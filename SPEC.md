# IELTS Assist - Specification Document

## Project Overview
- **Project Name**: IELTS Assist
- **Type**: Full-stack Web Application (PWA)
- **Core Functionality**: AI-powered personal IELTS preparation assistant that helps students track progress, analyze mistakes, practice tests, and review topics
- **Target Users**: IELTS test candidates (primarily Chinese-speaking students)

## Tech Stack
- **Frontend**: React 18 + Vite + TypeScript
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Styling**: CSS Modules + CSS Variables for theming
- **i18n**: react-i18next
- **State Management**: Zustand
- **HTTP Client**: Axios

## UI/UX Specification

### Color Palette
**Light Theme:**
- Primary: `#4F46E5` (Indigo)
- Primary Hover: `#4338CA`
- Secondary: `#10B981` (Emerald)
- Accent: `#F59E0B` (Amber)
- Background: `#F9FAFB`
- Surface: `#FFFFFF`
- Text Primary: `#111827`
- Text Secondary: `#6B7280`
- Border: `#E5E7EB`
- Error: `#EF4444`
- Success: `#10B981`

**Dark Theme:**
- Primary: `#818CF8` (Indigo Light)
- Primary Hover: `#A5B4FC`
- Secondary: `#34D399`
- Accent: `#FBBF24`
- Background: `#111827`
- Surface: `#1F2937`
- Text Primary: `#F9FAFB`
- Text Secondary: `#9CA3AF`
- Border: `#374151`
- Error: `#F87171`
- Success: `#34D399`

### Typography
- **Font Family**: `"Inter", "Noto Sans SC", system-ui, sans-serif`
- **Headings**:
  - H1: 32px, 700 weight
  - H2: 24px, 600 weight
  - H3: 20px, 600 weight
- **Body**: 16px, 400 weight
- **Small**: 14px, 400 weight

### Layout Structure
- **Sidebar**: 280px fixed width (collapsible on mobile)
- **Main Content**: Fluid, max-width 1200px
- **Header**: 64px height
- **Responsive Breakpoints**:
  - Mobile: < 768px
  - Tablet: 768px - 1024px
  - Desktop: > 1024px

### Components
1. **Navigation Sidebar**
   - Logo + App name
   - Navigation items with icons
   - Theme toggle
   - Language switcher
   - User profile section

2. **Dashboard Cards**
   - Progress rings for each skill
   - Recent activity timeline
   - Study streak counter
   - Upcoming goals

3. **Practice Modules**
   - Reading practice cards
   - Listening with audio player
   - Writing task prompts
   - Speaking topics

4. **Mistake Analyzer**
   - Category breakdown chart
   - Detailed mistake list
   - Improvement suggestions

5. **Topic Review**
   - Flashcard-style review
   - Spaced repetition system
   - Progress tracking

## Database Schema

### Tables
1. **users** - User accounts
2. **study_sessions** - Study time tracking
3. **practice_results** - Practice test results
4. **mistakes** - User's mistake records
5. **topics** - IELTS topics/vocabulary
6. **user_progress** - Skill progress per user
7. **goals** - Study goals

## Features

### Core Features
1. **Dashboard**
   - Overall progress overview
   - Study streak tracking
   - Recent activity
   - Quick actions

2. **Progress Tracking**
   - Band score calculator
   - Skill breakdown (Reading, Listening, Writing, Speaking)
   - Weekly/Monthly trends
   - Study time logging

3. **Practice Center**
   - Reading: Passages with questions
   - Listening: Audio with transcripts
   - Writing: Task 1 & Task 2 prompts
   - Speaking: Topic cards with timer

4. **Mistake Analysis**
   - Categorize mistakes by type
   - Track repeated mistakes
   - AI-powered suggestions
   - Progress over time

5. **Topic Review**
   - Vocabulary flashcards
   - Speaking topics
   - Writing ideas
   - Spaced repetition

6. **Goals & Reminders**
   - Daily/Weekly study goals
   - Test date countdown
   - Achievement badges

### Additional Features
7. **Statistics & Analytics**
   - Performance graphs
   - Time distribution
   - Weak areas identification

8. **Settings**
   - Theme toggle (Light/Dark)
   - Language switch (EN/中文)
   - Notification preferences
   - Test date setting

## API Endpoints

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

### Progress
- `GET /api/progress`
- `POST /api/progress`
- `GET /api/progress/stats`

### Practice
- `GET /api/practice/reading`
- `GET /api/practice/listening`
- `GET /api/practice/writing`
- `GET /api/practice/speaking`
- `POST /api/practice/submit`

### Mistakes
- `GET /api/mistakes`
- `POST /api/mistakes`
- `DELETE /api/mistakes/{id}`

### Topics
- `GET /api/topics`
- `POST /api/topics/review`
- `GET /api/topics/flashcards`

## Acceptance Criteria
1. ✓ User can register/login
2. ✓ Dashboard shows progress overview
3. ✓ Theme toggle works (light/dark)
4. ✓ Language switch works (EN/中文)
5. ✓ Can track study sessions
6. ✓ Can practice each skill
7. ✓ Can analyze mistakes
8. ✓ Can review topics with flashcards
9. ✓ Responsive design works on mobile
10. ✓ Modern, clean UI aesthetic