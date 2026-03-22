"""IELTS Speaking Part 2 — Cue card bank + metadata generator.

60+ curated cue cards across 8 domains. Pool seeding is instant (no GPT).
Same pattern as writing_config.py.
"""

import random

SPEAKING_DOMAINS = [
    "people", "places", "events", "objects",
    "experiences", "media", "education", "work",
]

PART2_CUE_CARDS = [
    # ── People ──────────────────────────────────────────────────────────
    {
        "id": "p2_ppl_01",
        "topic_title": "A Person Who Influenced You",
        "domain": "people",
        "topic_line": "Describe a person who has had a significant influence on your life.",
        "bullets": [
            "who this person is",
            "how you know them",
            "what they have done",
            "and explain why they have influenced you",
        ],
        "follow_up": "Do you think famous people have more influence than family members?",
    },
    {
        "id": "p2_ppl_02",
        "topic_title": "An Interesting Old Person You Met",
        "domain": "people",
        "topic_line": "Describe an interesting old person you have met.",
        "bullets": [
            "who this person is",
            "where you met them",
            "what you did or talked about together",
            "and explain why you found them interesting",
        ],
        "follow_up": "What can young people learn from older generations?",
    },
    {
        "id": "p2_ppl_03",
        "topic_title": "Someone Who Is Good at Cooking",
        "domain": "people",
        "topic_line": "Describe someone you know who is good at cooking.",
        "bullets": [
            "who this person is",
            "how you know them",
            "what kinds of food they cook",
            "and explain why you think they are good at cooking",
        ],
        "follow_up": "Do you think cooking skills are important in modern life?",
    },
    {
        "id": "p2_ppl_04",
        "topic_title": "A Famous Person You Admire",
        "domain": "people",
        "topic_line": "Describe a famous person you admire.",
        "bullets": [
            "who this person is",
            "how you first learned about them",
            "what they are famous for",
            "and explain why you admire them",
        ],
        "follow_up": "Do celebrities have a responsibility to be good role models?",
    },
    {
        "id": "p2_ppl_05",
        "topic_title": "A Neighbor You Know",
        "domain": "people",
        "topic_line": "Describe a neighbor you know well.",
        "bullets": [
            "who this person is",
            "how long you have known them",
            "what you do together or talk about",
            "and explain how you feel about this neighbor",
        ],
        "follow_up": "Is it important to have a good relationship with your neighbors?",
    },
    {
        "id": "p2_ppl_06",
        "topic_title": "A Teacher Who Influenced You",
        "domain": "people",
        "topic_line": "Describe a teacher who has had a great influence on your education.",
        "bullets": [
            "who this teacher is",
            "what subject they taught",
            "what made their teaching special",
            "and explain how they influenced you",
        ],
        "follow_up": "What qualities make a teacher truly effective?",
    },
    {
        "id": "p2_ppl_07",
        "topic_title": "A Friend From Childhood",
        "domain": "people",
        "topic_line": "Describe a friend you had when you were a child.",
        "bullets": [
            "who this friend was",
            "how you became friends",
            "what you used to do together",
            "and explain whether you are still in contact with them",
        ],
        "follow_up": "Why do some childhood friendships last while others fade away?",
    },
    {
        "id": "p2_ppl_08",
        "topic_title": "A Family Member You Spend Time With",
        "domain": "people",
        "topic_line": "Describe a family member you enjoy spending time with.",
        "bullets": [
            "who this person is",
            "what you usually do together",
            "how often you see them",
            "and explain why you enjoy their company",
        ],
        "follow_up": "How has the amount of time families spend together changed over the years?",
    },

    # ── Places ──────────────────────────────────────────────────────────
    {
        "id": "p2_plc_01",
        "topic_title": "Your Favorite Place in Your City",
        "domain": "places",
        "topic_line": "Describe your favorite place in the city where you live.",
        "bullets": [
            "where this place is",
            "what it looks like",
            "what you do there",
            "and explain why it is your favorite place",
        ],
        "follow_up": "Do you think cities need more public spaces for relaxation?",
    },
    {
        "id": "p2_plc_02",
        "topic_title": "A Place You Visited on Holiday",
        "domain": "places",
        "topic_line": "Describe a place you visited on holiday that you enjoyed.",
        "bullets": [
            "where this place is",
            "when you went there",
            "what you did there",
            "and explain why you enjoyed visiting this place",
        ],
        "follow_up": "Do you prefer to visit new places or return to places you already know?",
    },
    {
        "id": "p2_plc_03",
        "topic_title": "A Quiet Place You Like",
        "domain": "places",
        "topic_line": "Describe a quiet place you like to go to.",
        "bullets": [
            "where this place is",
            "how you found out about it",
            "how often you go there",
            "and explain why you like this quiet place",
        ],
        "follow_up": "Is it becoming harder to find quiet places in modern cities?",
    },
    {
        "id": "p2_plc_04",
        "topic_title": "A Crowded Place You Have Been To",
        "domain": "places",
        "topic_line": "Describe a crowded place you have been to.",
        "bullets": [
            "where this place is",
            "when you went there",
            "why it was so crowded",
            "and explain how you felt about being in this crowded place",
        ],
        "follow_up": "Why do some people enjoy being in crowded places?",
    },
    {
        "id": "p2_plc_05",
        "topic_title": "A Beautiful Garden or Park",
        "domain": "places",
        "topic_line": "Describe a beautiful garden or park you have visited.",
        "bullets": [
            "where it is located",
            "what it looks like",
            "what people do there",
            "and explain why you think it is beautiful",
        ],
        "follow_up": "Should governments invest more in public parks and green spaces?",
    },
    {
        "id": "p2_plc_06",
        "topic_title": "A Restaurant You Enjoy",
        "domain": "places",
        "topic_line": "Describe a restaurant you enjoy eating at.",
        "bullets": [
            "where it is",
            "what type of food it serves",
            "how often you eat there",
            "and explain why you enjoy this restaurant",
        ],
        "follow_up": "What makes a restaurant successful apart from the quality of food?",
    },
    {
        "id": "p2_plc_07",
        "topic_title": "A Historical Building You Have Visited",
        "domain": "places",
        "topic_line": "Describe a historical building you have visited.",
        "bullets": [
            "where this building is",
            "what it looks like",
            "what you learned about it",
            "and explain why you found it interesting",
        ],
        "follow_up": "Should old buildings be preserved or replaced with modern ones?",
    },
    {
        "id": "p2_plc_08",
        "topic_title": "A Place You Would Like to Live",
        "domain": "places",
        "topic_line": "Describe a place you would like to live in the future.",
        "bullets": [
            "where this place is",
            "how you learned about it",
            "what it is like there",
            "and explain why you would like to live in this place",
        ],
        "follow_up": "What factors are most important when choosing a place to live?",
    },

    # ── Events ──────────────────────────────────────────────────────────
    {
        "id": "p2_evt_01",
        "topic_title": "A Celebration You Attended",
        "domain": "events",
        "topic_line": "Describe a celebration or party you attended that you enjoyed.",
        "bullets": [
            "what the celebration was for",
            "where it took place",
            "what you did during the celebration",
            "and explain why you enjoyed it",
        ],
        "follow_up": "Are traditional celebrations becoming less important to young people?",
    },
    {
        "id": "p2_evt_02",
        "topic_title": "A Sports Event You Watched",
        "domain": "events",
        "topic_line": "Describe a sports event you watched that you found exciting.",
        "bullets": [
            "what the event was",
            "where and when you watched it",
            "who you watched it with",
            "and explain why it was exciting",
        ],
        "follow_up": "Do you think watching sports live is better than watching on TV?",
    },
    {
        "id": "p2_evt_03",
        "topic_title": "A Time You Helped Someone",
        "domain": "events",
        "topic_line": "Describe a time when you helped someone.",
        "bullets": [
            "who you helped",
            "what the situation was",
            "how you helped them",
            "and explain how you felt about helping this person",
        ],
        "follow_up": "Do people help others less than they used to?",
    },
    {
        "id": "p2_evt_04",
        "topic_title": "A Special Meal You Had",
        "domain": "events",
        "topic_line": "Describe a special meal you remember having.",
        "bullets": [
            "when and where you had this meal",
            "who you had it with",
            "what you ate",
            "and explain why it was special to you",
        ],
        "follow_up": "Why do people often associate food with important memories?",
    },
    {
        "id": "p2_evt_05",
        "topic_title": "A Time You Were Late",
        "domain": "events",
        "topic_line": "Describe a time when you were late for something important.",
        "bullets": [
            "when this happened",
            "why you were late",
            "what happened as a result",
            "and explain how you felt about being late",
        ],
        "follow_up": "Is punctuality more important in some cultures than others?",
    },
    {
        "id": "p2_evt_06",
        "topic_title": "An Important Decision You Made",
        "domain": "events",
        "topic_line": "Describe an important decision you had to make.",
        "bullets": [
            "what the decision was about",
            "what options you had",
            "how you made the decision",
            "and explain whether you think it was the right decision",
        ],
        "follow_up": "Do you think young people make decisions differently from older people?",
    },
    {
        "id": "p2_evt_07",
        "topic_title": "A Journey You Remember Well",
        "domain": "events",
        "topic_line": "Describe a journey you went on that you remember well.",
        "bullets": [
            "where you went",
            "how you traveled",
            "who you traveled with",
            "and explain why this journey is memorable",
        ],
        "follow_up": "Has the way people travel changed much in recent years?",
    },
    {
        "id": "p2_evt_08",
        "topic_title": "A Time You Received Good News",
        "domain": "events",
        "topic_line": "Describe a time when you received some good news.",
        "bullets": [
            "what the news was",
            "when and where you heard it",
            "who told you or how you found out",
            "and explain why it was good news for you",
        ],
        "follow_up": "Do people prefer to share good news in person or through messages?",
    },

    # ── Objects ─────────────────────────────────────────────────────────
    {
        "id": "p2_obj_01",
        "topic_title": "A Gift You Received",
        "domain": "objects",
        "topic_line": "Describe a gift you received that was special to you.",
        "bullets": [
            "what the gift was",
            "who gave it to you",
            "when you received it",
            "and explain why this gift was special",
        ],
        "follow_up": "Is it the thought behind a gift that matters most, or the gift itself?",
    },
    {
        "id": "p2_obj_02",
        "topic_title": "Something You Bought Recently",
        "domain": "objects",
        "topic_line": "Describe something you bought recently that you are happy with.",
        "bullets": [
            "what you bought",
            "where you bought it",
            "why you decided to buy it",
            "and explain why you are happy with this purchase",
        ],
        "follow_up": "Do you think people buy too many things they do not really need?",
    },
    {
        "id": "p2_obj_03",
        "topic_title": "A Piece of Technology You Use Often",
        "domain": "objects",
        "topic_line": "Describe a piece of technology you use every day.",
        "bullets": [
            "what the technology is",
            "when you started using it",
            "what you use it for",
            "and explain how it has made your life easier",
        ],
        "follow_up": "Are people becoming too dependent on technology?",
    },
    {
        "id": "p2_obj_04",
        "topic_title": "An Old Object You Keep",
        "domain": "objects",
        "topic_line": "Describe an old object that you keep and value.",
        "bullets": [
            "what the object is",
            "how long you have had it",
            "where you keep it",
            "and explain why it is valuable to you",
        ],
        "follow_up": "Why do some people like to collect old objects?",
    },
    {
        "id": "p2_obj_05",
        "topic_title": "A Photograph You Like",
        "domain": "objects",
        "topic_line": "Describe a photograph that you particularly like.",
        "bullets": [
            "what is in the photograph",
            "when it was taken",
            "who took it",
            "and explain why you like this photograph",
        ],
        "follow_up": "Has digital photography changed the way people take pictures?",
    },
    {
        "id": "p2_obj_06",
        "topic_title": "A Book That Influenced You",
        "domain": "objects",
        "topic_line": "Describe a book you read that had a strong influence on you.",
        "bullets": [
            "what the book was about",
            "when you read it",
            "why you decided to read it",
            "and explain how it influenced you",
        ],
        "follow_up": "Do you think people read less now compared to the past?",
    },
    {
        "id": "p2_obj_07",
        "topic_title": "A Piece of Clothing You Like",
        "domain": "objects",
        "topic_line": "Describe a piece of clothing you especially like wearing.",
        "bullets": [
            "what it is",
            "where you got it",
            "when you usually wear it",
            "and explain why you like this piece of clothing",
        ],
        "follow_up": "How important is fashion to people in your country?",
    },
    {
        "id": "p2_obj_08",
        "topic_title": "A Piece of Art You Enjoyed",
        "domain": "objects",
        "topic_line": "Describe a piece of art, such as a painting or sculpture, that you have seen and liked.",
        "bullets": [
            "what the artwork was",
            "where you saw it",
            "what it looked like",
            "and explain why you liked it",
        ],
        "follow_up": "Should art education be a required subject in schools?",
    },

    # ── Experiences ─────────────────────────────────────────────────────
    {
        "id": "p2_exp_01",
        "topic_title": "A Skill You Learned",
        "domain": "experiences",
        "topic_line": "Describe a useful skill you learned.",
        "bullets": [
            "what the skill is",
            "how you learned it",
            "how long it took you to learn",
            "and explain why this skill is useful",
        ],
        "follow_up": "What skills do you think will be most important in the future?",
    },
    {
        "id": "p2_exp_02",
        "topic_title": "A Time You Got Lost",
        "domain": "experiences",
        "topic_line": "Describe a time when you got lost.",
        "bullets": [
            "where you were going",
            "how you got lost",
            "what you did to find your way",
            "and explain how you felt during this experience",
        ],
        "follow_up": "Do GPS and map apps mean people will never get lost anymore?",
    },
    {
        "id": "p2_exp_03",
        "topic_title": "A Time You Waited for Something",
        "domain": "experiences",
        "topic_line": "Describe a time when you had to wait a long time for something.",
        "bullets": [
            "what you were waiting for",
            "where you were waiting",
            "how long you had to wait",
            "and explain how you felt while waiting",
        ],
        "follow_up": "Are people less patient now than they were in the past?",
    },
    {
        "id": "p2_exp_04",
        "topic_title": "An Achievement You Are Proud Of",
        "domain": "experiences",
        "topic_line": "Describe an achievement you are proud of.",
        "bullets": [
            "what you achieved",
            "when it happened",
            "how difficult it was",
            "and explain why you are proud of this achievement",
        ],
        "follow_up": "Is it important to celebrate personal achievements?",
    },
    {
        "id": "p2_exp_05",
        "topic_title": "A Time You Tried New Food",
        "domain": "experiences",
        "topic_line": "Describe a time when you tried a type of food for the first time.",
        "bullets": [
            "what the food was",
            "where you tried it",
            "what it tasted like",
            "and explain whether you would eat it again",
        ],
        "follow_up": "Why are some people unwilling to try food from other cultures?",
    },
    {
        "id": "p2_exp_06",
        "topic_title": "A Time You Stayed Up Late",
        "domain": "experiences",
        "topic_line": "Describe a time when you stayed up very late.",
        "bullets": [
            "when this happened",
            "why you stayed up late",
            "what you were doing",
            "and explain how you felt the next day",
        ],
        "follow_up": "Do you think young people stay up later than older people?",
    },
    {
        "id": "p2_exp_07",
        "topic_title": "A Time You Felt Excited",
        "domain": "experiences",
        "topic_line": "Describe a time when you felt really excited about something.",
        "bullets": [
            "what it was about",
            "when it happened",
            "what you did because of the excitement",
            "and explain why you felt so excited",
        ],
        "follow_up": "Do adults get excited about things as easily as children do?",
    },
    {
        "id": "p2_exp_08",
        "topic_title": "A Risk You Took",
        "domain": "experiences",
        "topic_line": "Describe a time when you took a risk and it was worth it.",
        "bullets": [
            "what the risk was",
            "why you decided to take it",
            "what happened as a result",
            "and explain why you think it was worth taking the risk",
        ],
        "follow_up": "Do you think taking risks is necessary for success?",
    },

    # ── Media ───────────────────────────────────────────────────────────
    {
        "id": "p2_med_01",
        "topic_title": "A Movie You Enjoyed",
        "domain": "media",
        "topic_line": "Describe a movie you watched recently that you enjoyed.",
        "bullets": [
            "what the movie was about",
            "when and where you watched it",
            "who you watched it with",
            "and explain why you enjoyed this movie",
        ],
        "follow_up": "Do you think movies today are better than movies from the past?",
    },
    {
        "id": "p2_med_02",
        "topic_title": "A TV Program You Watch Regularly",
        "domain": "media",
        "topic_line": "Describe a TV program you watch regularly.",
        "bullets": [
            "what the program is about",
            "how often you watch it",
            "who you usually watch it with",
            "and explain why you enjoy this program",
        ],
        "follow_up": "Has streaming changed the way people watch television?",
    },
    {
        "id": "p2_med_03",
        "topic_title": "A Website You Use Often",
        "domain": "media",
        "topic_line": "Describe a website you visit often.",
        "bullets": [
            "what the website is",
            "what type of content it has",
            "how often you visit it",
            "and explain why you find it useful or enjoyable",
        ],
        "follow_up": "Do you think the internet has more positive or negative effects on society?",
    },
    {
        "id": "p2_med_04",
        "topic_title": "A Song You Remember Well",
        "domain": "media",
        "topic_line": "Describe a song that you remember well and like to listen to.",
        "bullets": [
            "what the song is called",
            "when you first heard it",
            "what the song is about",
            "and explain why you like this song",
        ],
        "follow_up": "Why do certain songs bring back strong memories?",
    },
    {
        "id": "p2_med_05",
        "topic_title": "An Advertisement You Remember",
        "domain": "media",
        "topic_line": "Describe an advertisement you remember well.",
        "bullets": [
            "where you saw or heard it",
            "what it was advertising",
            "what happened in the advertisement",
            "and explain why you remember it",
        ],
        "follow_up": "Do you think advertisements influence what people buy?",
    },
    {
        "id": "p2_med_06",
        "topic_title": "A News Story You Read About",
        "domain": "media",
        "topic_line": "Describe an interesting news story you read or heard about recently.",
        "bullets": [
            "what the story was about",
            "where you heard or read about it",
            "why it was in the news",
            "and explain why you found it interesting",
        ],
        "follow_up": "How do most people in your country get their news?",
    },
    {
        "id": "p2_med_07",
        "topic_title": "A Podcast or Radio Show You Like",
        "domain": "media",
        "topic_line": "Describe a podcast or radio program you enjoy listening to.",
        "bullets": [
            "what it is called",
            "what topics it covers",
            "how often you listen to it",
            "and explain what makes it enjoyable for you",
        ],
        "follow_up": "Do you think podcasts will replace traditional radio?",
    },
    {
        "id": "p2_med_08",
        "topic_title": "A Social Media Experience",
        "domain": "media",
        "topic_line": "Describe an interesting experience you had on social media.",
        "bullets": [
            "what happened",
            "which platform it was on",
            "who was involved",
            "and explain why this experience was memorable",
        ],
        "follow_up": "Do you think social media brings people closer together or pushes them apart?",
    },

    # ── Education ───────────────────────────────────────────────────────
    {
        "id": "p2_edu_01",
        "topic_title": "A Subject You Enjoyed at School",
        "domain": "education",
        "topic_line": "Describe a subject you enjoyed studying at school.",
        "bullets": [
            "what the subject was",
            "who taught it",
            "what you learned in this subject",
            "and explain why you enjoyed it",
        ],
        "follow_up": "Should students be allowed to choose all their own subjects?",
    },
    {
        "id": "p2_edu_02",
        "topic_title": "A Course You Would Like to Take",
        "domain": "education",
        "topic_line": "Describe a course or training program you would like to take.",
        "bullets": [
            "what the course would be about",
            "where you would take it",
            "how long it would last",
            "and explain why you are interested in this course",
        ],
        "follow_up": "Is online learning as effective as traditional classroom learning?",
    },
    {
        "id": "p2_edu_03",
        "topic_title": "A Time You Taught Someone Something",
        "domain": "education",
        "topic_line": "Describe a time when you taught something to another person.",
        "bullets": [
            "who you taught",
            "what you taught them",
            "how you taught them",
            "and explain how you felt about the experience",
        ],
        "follow_up": "Is teaching others a good way to deepen your own understanding?",
    },
    {
        "id": "p2_edu_04",
        "topic_title": "A School Rule You Remember",
        "domain": "education",
        "topic_line": "Describe a rule at your school that you remember well.",
        "bullets": [
            "what the rule was",
            "why the school had this rule",
            "how students felt about it",
            "and explain whether you think the rule was fair",
        ],
        "follow_up": "Are school rules too strict or not strict enough these days?",
    },
    {
        "id": "p2_edu_05",
        "topic_title": "A Project You Worked On",
        "domain": "education",
        "topic_line": "Describe a project you worked on at school or university.",
        "bullets": [
            "what the project was about",
            "who you worked with",
            "what you had to do",
            "and explain what you learned from doing this project",
        ],
        "follow_up": "Do group projects help students develop important skills?",
    },
    {
        "id": "p2_edu_06",
        "topic_title": "A Presentation You Gave",
        "domain": "education",
        "topic_line": "Describe a presentation or talk you gave to a group of people.",
        "bullets": [
            "what the presentation was about",
            "who the audience was",
            "how you prepared for it",
            "and explain how you felt about giving the presentation",
        ],
        "follow_up": "Why do many people find public speaking difficult?",
    },
    {
        "id": "p2_edu_07",
        "topic_title": "Something New You Learned Recently",
        "domain": "education",
        "topic_line": "Describe something new you learned recently that you found interesting.",
        "bullets": [
            "what you learned",
            "how you learned it",
            "why you decided to learn it",
            "and explain why it was interesting to you",
        ],
        "follow_up": "Is it more important to learn practical skills or academic knowledge?",
    },
    {
        "id": "p2_edu_08",
        "topic_title": "An Educational Trip You Went On",
        "domain": "education",
        "topic_line": "Describe an educational trip or visit you went on.",
        "bullets": [
            "where you went",
            "when you went there",
            "what you saw or did",
            "and explain what you learned from this trip",
        ],
        "follow_up": "Are school trips an effective way for students to learn?",
    },

    # ── Work ────────────────────────────────────────────────────────────
    {
        "id": "p2_wrk_01",
        "topic_title": "A Job You Would Like to Try",
        "domain": "work",
        "topic_line": "Describe a job you would like to try in the future.",
        "bullets": [
            "what the job is",
            "what skills it requires",
            "how you learned about this job",
            "and explain why you would like to try it",
        ],
        "follow_up": "Is it better to follow your passion or choose a well-paid career?",
    },
    {
        "id": "p2_wrk_02",
        "topic_title": "A Time You Worked in a Team",
        "domain": "work",
        "topic_line": "Describe a time when you worked in a team to complete a task.",
        "bullets": [
            "what the task was",
            "who was on your team",
            "what your role was",
            "and explain how well the team worked together",
        ],
        "follow_up": "What are the advantages and disadvantages of teamwork?",
    },
    {
        "id": "p2_wrk_03",
        "topic_title": "A Busy Time at Work or Study",
        "domain": "work",
        "topic_line": "Describe a time when you were very busy with work or studies.",
        "bullets": [
            "when this was",
            "what you had to do",
            "how you managed your time",
            "and explain how you felt during this busy period",
        ],
        "follow_up": "Do you think people are busier today than they were in the past?",
    },
    {
        "id": "p2_wrk_04",
        "topic_title": "A Company You Would Like to Work For",
        "domain": "work",
        "topic_line": "Describe a company or organization you would like to work for.",
        "bullets": [
            "what the company does",
            "how you know about it",
            "what kind of work you would do there",
            "and explain why you would like to work for this company",
        ],
        "follow_up": "What makes a company a good place to work?",
    },
    {
        "id": "p2_wrk_05",
        "topic_title": "A Skill Useful for Your Work",
        "domain": "work",
        "topic_line": "Describe a skill that is useful for your work or studies.",
        "bullets": [
            "what the skill is",
            "how you developed this skill",
            "how often you use it",
            "and explain why it is important for your work or studies",
        ],
        "follow_up": "Which skills do employers value most in the modern workplace?",
    },
    {
        "id": "p2_wrk_06",
        "topic_title": "A Meeting You Attended",
        "domain": "work",
        "topic_line": "Describe an important meeting you attended.",
        "bullets": [
            "what the meeting was about",
            "who was at the meeting",
            "what was discussed or decided",
            "and explain why this meeting was important",
        ],
        "follow_up": "Do you think too many meetings are held in the workplace?",
    },
    {
        "id": "p2_wrk_07",
        "topic_title": "A Time You Had Too Much Work",
        "domain": "work",
        "topic_line": "Describe a time when you felt you had too much work to do.",
        "bullets": [
            "what work you had to do",
            "why there was so much work",
            "how you dealt with the situation",
            "and explain how you felt about having too much work",
        ],
        "follow_up": "How can people achieve a better work-life balance?",
    },
    {
        "id": "p2_wrk_08",
        "topic_title": "A Successful Project You Completed",
        "domain": "work",
        "topic_line": "Describe a project at work or in your studies that was successful.",
        "bullets": [
            "what the project was about",
            "what your role was",
            "what made it successful",
            "and explain how you felt when the project was completed",
        ],
        "follow_up": "What do you think is the key to a successful project?",
    },
]


def generate_metadata(
    avoid_topics: list[str] | None = None,
    avoid_domains: list[str] | None = None,
) -> dict | None:
    """Pick a cue card avoiding recent topics/domains. Returns cue card dict or None."""
    avoid_topics = set(avoid_topics or [])
    avoid_domains = set(avoid_domains or [])

    candidates = [
        c for c in PART2_CUE_CARDS
        if c["topic_title"] not in avoid_topics
        and c["domain"] not in avoid_domains
    ]

    if not candidates:
        candidates = [
            c for c in PART2_CUE_CARDS
            if c["topic_title"] not in avoid_topics
        ]

    if not candidates:
        return None

    return random.choice(candidates)
