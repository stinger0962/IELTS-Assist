import { describe, it, expect } from 'vitest'
import type { SkillType, ReadingExercise } from '../types'

describe('Type Definitions', () => {
  it('should accept valid skill types', () => {
    const skills: SkillType[] = ['reading', 'listening', 'writing', 'speaking']
    expect(skills).toHaveLength(4)
    expect(skills).toContain('reading')
    expect(skills).toContain('listening')
    expect(skills).toContain('writing')
    expect(skills).toContain('speaking')
  })

  it('should create a valid ReadingExercise structure', () => {
    const exercise: ReadingExercise = {
      id: 'test-001',
      passage: 'This is a test passage about urban planning.',
      questions: [
        {
          id: 'q1',
          text: 'What is the passage about?',
          options: ['Science', 'Urban planning', 'Music', 'Sports'],
          correctIndex: 1,
        },
      ],
    }
    expect(exercise.id).toBe('test-001')
    expect(exercise.passage).toBeTruthy()
    expect(exercise.questions).toHaveLength(1)
    expect(exercise.questions[0].correctIndex).toBe(1)
  })
})
