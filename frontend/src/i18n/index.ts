import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: {
      studyPass: {
        title: '30-day study pass',
        legacy: 'Your existing VIP access is unchanged.',
        usedTrial: 'Your free writing review has been used.',
        description: 'One-time access, no automatic renewal.',
        active: 'Pass active',
        expires: 'Expires {{date}}',
        remaining: '{{count}} writing reviews remaining',
        expired: 'Your pass has expired. Basic practice remains free.',
        trial: 'Try one free AI writing review before choosing a pass.',
        details: 'What is included?',
        mocks: 'Full reading and listening mock tests.',
        reviews: 'A capped allowance of AI writing feedback, not unlimited reviews.',
        basic: 'Basic practice stays free.',
        unavailable: 'Purchasing is not available yet. No payment will be taken.',
        disclaimer: 'AI feedback is for practice, not an official IELTS score or score guarantee.',
        required: 'A study pass or available writing review is required. Your essay is still here; you can continue editing or copy it.',
        failed: 'Grading failed. Please try again.',
        feedback: 'Your essay will receive AI feedback.',
      },
      app: {
        name: 'IELTS Assist',
        tagline: 'Your Personal IELTS Preparation Assistant'
      },
      nav: {
        dashboard: 'Dashboard',
        practice: 'Practice',
        mistakes: 'Mistakes',
        topics: 'Topics',
        goals: 'Goals',
        settings: 'Settings'
      },
      dashboard: {
        welcome: 'Welcome back!',
        studyStreak: 'Study Streak',
        days: 'days',
        totalStudyTime: 'Total Study Time',
        hours: 'hours',
        avgBand: 'Average Band',
        recentActivity: 'Recent Activity',
        quickActions: 'Quick Actions',
        startPractice: 'Start Practice',
        reviewMistakes: 'Review Mistakes',
        reviewTopics: 'Review Topics',
        noActivity: 'No recent activity'
      },
      skills: {
        reading: 'Reading',
        listening: 'Listening',
        writing: 'Writing',
        speaking: 'Speaking',
        grammar: 'Grammar',
        progress: 'Progress',
        bandScore: 'Band Score',
        exercises: 'Exercises',
        timeSpent: 'Time Spent',
        minutes: 'min'
      },
      practice: {
        title: 'Practice Center',
        reading: 'Reading Practice',
        listening: 'Listening Practice',
        writing: 'Writing Practice',
        speaking: 'Speaking Practice',
        grammar: 'Grammar',
        selectExercise: 'Select an exercise to begin',
        submit: 'Submit',
        next: 'Next',
        finish: 'Finish',
        score: 'Score',
        correct: 'Correct',
        incorrect: 'Incorrect',
        timeSpent: 'Time Spent',
        seconds: 'seconds'
      },
      mistakes: {
        title: 'Mistake Analysis',
        noMistakes: 'No mistakes recorded yet',
        question: 'Question',
        yourAnswer: 'Your Answer',
        correctAnswer: 'Correct Answer',
        type: 'Type',
        repeated: 'Times Repeated',
        explanation: 'Explanation',
        delete: 'Delete',
        review: 'Review'
      },
      topics: {
        title: 'Topic Review',
        flashcards: 'Flashcards',
        vocabulary: 'Vocabulary',
        grammar: 'Grammar',
        ideas: 'Ideas',
        showAnswer: 'Show Answer',
        next: 'Next',
        difficulty: 'Difficulty',
        category: 'Category',
        again: 'Again',
        hard: 'Hard',
        good: 'Good',
        easy: 'Easy'
      },
      goals: {
        title: 'Goals',
        addGoal: 'Add Goal',
        targetDate: 'Target Date',
        targetMinutes: 'Target Minutes/Day',
        completed: 'Completed',
        active: 'Active',
        markComplete: 'Mark Complete',
        delete: 'Delete',
        noGoals: 'No goals yet'
      },
      auth: {
        login: 'Login',
        register: 'Register',
        email: 'Email',
        password: 'Password',
        username: 'Username',
        fullName: 'Full Name',
        noAccount: "Don't have an account?",
        haveAccount: 'Already have an account?',
        logout: 'Logout'
      },
      settings: {
        title: 'Settings',
        language: 'Language',
        theme: 'Theme',
        light: 'Light',
        dark: 'Dark',
        targetBand: 'Target Band Score',
        testDate: 'Test Date',
        save: 'Save Changes'
      },
      common: {
        loading: 'Loading...',
        error: 'An error occurred',
        save: 'Save',
        cancel: 'Cancel',
        delete: 'Delete',
        edit: 'Edit',
        close: 'Close'
      }
    }
  },
  zh: {
    translation: {
      studyPass: {
        title: '30天学习通行证',
        legacy: '你现有的 VIP 权益保持不变。',
        usedTrial: '免费写作批改次数已用完。',
        description: '一次购买，不自动续费。',
        active: '通行证有效',
        expires: '到期日期：{{date}}',
        remaining: '剩余 {{count}} 次写作批改',
        expired: '通行证已到期，基础练习仍然免费。',
        trial: '选择通行证前，可免费体验一次 AI 写作批改。',
        details: '包含哪些功能？',
        mocks: '完整阅读和听力模拟考试。',
        reviews: '限额 AI 写作反馈，并非无限次批改。',
        basic: '基础练习保持免费。',
        unavailable: '暂未开放购买，不会收取任何费用。',
        disclaimer: 'AI 反馈仅供练习参考，不是雅思官方评分，也不保证考试成绩。',
        required: '需要有效通行证或可用写作次数。作文仍保留在此处，可继续编辑或复制。',
        failed: '批改失败，请重试。',
        feedback: '你的作文将获得 AI 反馈。',
      },
      app: {
        name: 'IELTS助手',
        tagline: '您的个人雅思备考助手'
      },
      nav: {
        dashboard: '主页',
        practice: '练习',
        mistakes: '错题分析',
        topics: '话题复习',
        goals: '目标',
        settings: '设置'
      },
      dashboard: {
        welcome: '欢迎回来！',
        studyStreak: '连续学习',
        days: '天',
        totalStudyTime: '总学习时间',
        hours: '小时',
        avgBand: '平均分数',
        recentActivity: '最近活动',
        quickActions: '快捷操作',
        startPractice: '开始练习',
        reviewMistakes: '复习错题',
        reviewTopics: '复习话题',
        noActivity: '暂无活动记录'
      },
      skills: {
        reading: '阅读',
        listening: '听力',
        writing: '写作',
        speaking: '口语',
        grammar: '语法',
        progress: '进度',
        bandScore: '目标分数',
        exercises: '练习数',
        timeSpent: '学习时间',
        minutes: '分钟'
      },
      practice: {
        title: '练习中心',
        reading: '阅读练习',
        listening: '听力练习',
        writing: '写作练习',
        speaking: '口语练习',
        grammar: '语法练习',
        selectExercise: '选择一个练习开始',
        submit: '提交',
        next: '下一题',
        finish: '完成',
        score: '得分',
        correct: '正确',
        incorrect: '错误',
        timeSpent: '用时',
        seconds: '秒'
      },
      mistakes: {
        title: '错题分析',
        noMistakes: '暂无错题记录',
        question: '题目',
        yourAnswer: '你的答案',
        correctAnswer: '正确答案',
        type: '类型',
        repeated: '重复次数',
        explanation: '解释',
        delete: '删除',
        review: '复习'
      },
      topics: {
        title: '话题复习',
        flashcards: '闪卡',
        vocabulary: '词汇',
        grammar: '语法',
        ideas: '观点',
        showAnswer: '显示答案',
        next: '下一个',
        difficulty: '难度',
        category: '分类',
        again: '重来',
        hard: '困难',
        good: '一般',
        easy: '简单'
      },
      goals: {
        title: '目标',
        addGoal: '添加目标',
        targetDate: '目标日期',
        targetMinutes: '目标分钟/天',
        completed: '已完成',
        active: '进行中',
        markComplete: '标记完成',
        delete: '删除',
        noGoals: '暂无目标'
      },
      auth: {
        login: '登录',
        register: '注册',
        email: '邮箱',
        password: '密码',
        username: '用户名',
        fullName: '姓名',
        noAccount: '还没有账号？',
        haveAccount: '已有账号？',
        logout: '退出登录'
      },
      settings: {
        title: '设置',
        language: '语言',
        theme: '主题',
        light: '浅色',
        dark: '深色',
        targetBand: '目标分数',
        testDate: '考试日期',
        save: '保存'
      },
      common: {
        loading: '加载中...',
        error: '发生错误',
        save: '保存',
        cancel: '取消',
        delete: '删除',
        edit: '编辑',
        close: '关闭'
      }
    }
  }
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: 'en',
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;