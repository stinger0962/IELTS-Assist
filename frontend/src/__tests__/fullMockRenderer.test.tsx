import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AIReadingFullTestView from '../components/practice/AIReadingFullTestView';
import AIListeningFullTestView from '../components/practice/AIListeningFullTestView';
import { practiceAPI } from '../api';
import fixtures from './fixtures/fullMockRenderer.json';

vi.mock('../api', () => ({
  practiceAPI: { submitReadingExam: vi.fn(), submitListeningExam: vi.fn() },
  progressAPI: { updateProgress: vi.fn(), createSession: vi.fn() },
}));
vi.mock('../hooks/useVocabSelection', () => ({ useVocabSelection: () => ({}) }));
vi.mock('../components/Celebrations', () => ({ ConfettiBurst: () => null, CountUp: () => null }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
  // Stay in processing: these tests inspect the real outgoing payload, not
  // result rendering, progress calls or any server/network interaction.
  vi.mocked(practiceAPI.submitReadingExam).mockImplementation(() => new Promise(() => {}));
  vi.mocked(practiceAPI.submitListeningExam).mockImplementation(() => new Promise(() => {}));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function fillCurrentSection(container: HTMLElement, section: number) {
  // Actions operate actual DOM controls; IDs are not copied from component code.
  const inputs = container.querySelectorAll<HTMLInputElement>('input[type="text"]');
  inputs.forEach((input, i) => {
    const value = `section-${section}-input-${i}`;
    fireEvent.change(input, { target: { value } });
  });
  container.querySelectorAll<HTMLSelectElement>('select').forEach(select => {
    fireEvent.change(select, { target: { value: 'A' } });
  });
  container.querySelectorAll<HTMLElement>('.rft-mcq-opts, .mcq-options').forEach(group => {
    fireEvent.click(group.querySelector('button')!);
  });
}

function assertKeys(
  sections: Array<{ section_number: number; answers: Record<string, string> }>,
  maps: Record<string, Record<string, string>>,
) {
  expect(sections).toHaveLength(Object.keys(maps).length);
  for (const section of sections) {
    expect(Object.keys(section.answers).sort()).toEqual(Object.keys(maps[String(section.section_number)]).sort());
    expect(Object.values(section.answers).every(answer => answer.length > 0)).toBe(true);
  }
}

describe('Pinned actual full-test renderer submission contract', () => {
  it('Reading emits section-scoped indices, MCQ numbers and heading identities', async () => {
    const { container } = render(<AIReadingFullTestView exercise={fixtures.reading.exercise} onBack={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start Exam' }));
    for (let section = 1; section <= 3; section++) {
      fillCurrentSection(container, section);
      fireEvent.click(screen.getByRole('button', { name: section < 3 ? 'Next Section' : 'Submit Exam' }));
    }
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /^Submit$/ })); });
    const [id, sections] = vi.mocked(practiceAPI.submitReadingExam).mock.calls[0];
    expect(id).toBe(712);
    assertKeys(sections, fixtures.reading.keys);
    expect(sections[0].answers.q_0_0).toBe('section-1-input-0');
    expect(sections[1].answers.q_0_0).toBe('section-2-input-0');
    expect(sections[0].answers.q_1_11).toBe('A');
    expect(sections[0].answers.mh_2_1).toBe('A');
    expect(sections[0].answers.mh_2_2).toBe('A');
  });

  it.each(['listening', 'listeningEmpty'] as const)(
    '%s emits frontend completion/matching/MCQ group order, without empty group slots',
    async name => {
      const fixture = fixtures[name];
      const { container } = render(<AIListeningFullTestView exercise={fixture.exercise} onBack={() => {}} />);
      fireEvent.click(screen.getByRole('button', { name: 'Start Exam' }));
      for (let section = 1; section <= 4; section++) {
        fillCurrentSection(container, section);
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Start Audio Now' })); });
        fireEvent.click(screen.getByRole('button', { name: 'Skip Audio →' }));
        fireEvent.click(screen.getByRole('button', { name: section < 4 ? 'Next Section →' : 'Review Answers →' }));
      }
      fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: /^Submit$/ })); });
      const [id, sections] = vi.mocked(practiceAPI.submitListeningExam).mock.calls[0];
      expect(id).toBe(712);
      assertKeys(sections, fixture.keys);
      if (name === 'listening') {
        expect(sections[0].answers.q_0_0).toBe('section-1-input-0');
        expect(sections[0].answers.q_1_0).toBe('A'); // Matching stem, not MCQ
        expect(sections[0].answers.q_1_1).toBe('A');
        expect(sections[0].answers.q_2_0).toBe('A');
      } else {
        expect(sections[0].answers.q_0_0).toBe('A'); // First matching block
        expect(sections[0].answers.q_1_0).toBe('A'); // Second matching block
        expect(sections[0].answers.q_2_0).toBe('A'); // MCQ follows both blocks
      }
    },
    15_000,
  );
});
