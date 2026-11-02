# AI Coding Rules: Universal Guide for Developers and AI Agents

Comprehensive system of 9 rules for effective AI-assisted development based on 2025 best practices. Use these rules in every project by cloning this repository as a template.

---

## 🎯 Rule 1: Ответственность за ошибки

**Objective:** Exclude AI blame-shifting; focus on input quality.

**Steps:**
1. Analyze context for contradictions/garbage
2. Clarify instructions (specific, with examples)
3. Add success criteria (tests, linters)

**Success Criteria:** No bugs in 80% of cases; for rare stacks – external search

**AI Prompt:**
```
Проверь контекст на ошибки. Если неясно — спроси. Исправь код по тестам: [тесты]
```

---

## 📦 Rule 2: Подготовка контекста

**Objective:** Give AI the complete project picture top-to-bottom.

**Steps:**
1. Load architecture, subsystems, interactions
2. Warm up Memory Bank (study repository)
3. Focus on task after overview

**Success Criteria:** Context in CONTEXT.md < 10k tokens, no random fragments

**AI Prompt:**
```
Изучи проект: архитектура из CONTEXT.md. Подтверди понимание перед кодом.
```

---

## 📋 Rule 3: Обязательное планирование

**Objective:** Avoid chaotic code; plan as a contract.

**Steps:**
1. Generate plan in .md (points, files, tests)
2. Approve before implementation
3. Execute by points sequentially

**Success Criteria:** Plan covers 100% of task; saved in git

**AI Prompt:**
```
Создай план в PLAN.md: 1. Файлы. 2. Логика. 3. Тесты. Утверди перед кодом.
```

---

## ✅ Rule 4: Приёмка через тесты

**Objective:** Automated verification instead of code review.

**Steps:**
1. Discuss tests early (e2e > unit)
2. AI self-checks
3. Run CI

**Success Criteria:** 100% scenario coverage; green tests

**AI Prompt:**
```
Напиши тесты по критериям: [список]. Запусти и отчитайся: passed/failed.
```

---

## 🔍 Rule 5: Верификация плана

**Objective:** Synchronize implementation with plan.

**Steps:**
1. Open PLAN.md
2. Report: point → file/test
3. Rework on gaps

**Success Criteria:** All points "done" with evidence

**AI Prompt:**
```
Сверь с PLAN.md: для пункта 1 — файлы X, тесты Y. Отчёт в VERIFY.md.
```

---

## 🔗 Rule 6: Git-гигиена

**Objective:** Rollback ability and traceability.

**Steps:** Commit at stages: plan, point, tests. Messages: "Rule3: Plan approved"

**Success Criteria:** No "monster commits"; readable git log

**AI Prompt:**
```
Предложи git commit: 'Rule4: Tests for [feature]' после зелёных тестов.
```

---

## 📐 Rule 7: Работа по SDD

**Objective:** Structured specification before code.

**Steps:**
1. Fill SDD-TEMPLATE.md (architecture, models, API)
2. AI generates artifacts sequentially
3. Fix changes

**Success Criteria:** SDD covers domain; verified by tests

**AI Prompt:**
```
Заполни SDD-MICRO.md по требованиям. Генерируй код только после утверждения.
```

---

## 🔄 Rule 8: Формирование и актуализация контекста

**Objective:** Living project context.

**Steps:**
1. Initialize CONTEXT.md
2. After stage: diff + update
3. AI confirmation

**Success Criteria:** No contradictions; version in git

**AI Prompt:**
```
Обнови CONTEXT.md: git diff + новые зависимости. Подтверди: 'Контекст актуален'.
```

---

## 🏗️ Rule 9: Микросервисная архитектура

**Objective:** Scalability and service isolation.

**Steps:**
1. In SDD: Bounded Contexts, API contracts, events
2. Generate from service-template (layers, Docker)
3. Test coupling/faults

**Success Criteria:** Loose coupling; observability (logs/metrics)

**AI Prompt:**
```
По SDD-MICRO.md: генерируй сервис [name]. Контракт OpenAPI, события Kafka, тесты изоляции.
```

---

## 📁 Repository Structure

```
ai-coding-rules-template/
├── AI-RULES.md                 # This file - all 9 rules with prompts
├── README.md                   # Quick start guide
├── docs/
│   ├── SDD-TEMPLATE.md         # System Design Document template
│   ├── SDD-MICRO.md            # Microservices SDD template
│   ├── CONTEXT.md              # Project context (copy & adapt)
│   └── MICROservices-RULES.md  # Microservices rules details
├── examples/
│   ├── task-planning.md        # Example task plan
│   ├── sdd-example.md          # Example SDD completion
│   └── microservice-example/   # Working microservice example
├── scripts/
│   └── update-context.sh       # Script to update CONTEXT.md
├── .github/
│   └── workflows/
│       └── ai-check.yml        # CI: validates plans, tests, SDD
├── .gitignore
├── LICENSE (MIT)
└── .gitattributes
```

---

## 🚀 Quick Start

1. **Clone as template:** GitHub → "Use this template" → Create new repository
2. **Fill CONTEXT.md** with your project architecture
3. **Generate SDD-TEMPLATE.md** for current task
4. **Follow rules 1-9** for every task: Plan → Code → Test → Verify → Commit
5. **Reference in AI prompts:** "Follow AI-RULES.md from https://github.com/flakeman/ai-coding-rules-template"

---

## 📌 Key Principles

- **Planning First:** No code without approved plan
- **Tests Prove:** Tests are the acceptance criteria
- **Context Alive:** Update context after each stage
- **Git Traces:** Each rule = git commit
- **SDD Drives:** Architecture comes before implementation
- **Microservices:** Bounded contexts, loose coupling, observability

---

## 🔧 For AI Agents (Cursor, Claude, Copilot)

Add this to your system prompt:
```
You MUST follow 9 AI Coding Rules from: 
https://github.com/flakeman/ai-coding-rules-template/blob/main/AI-RULES.md

For every project task:
1. Read CONTEXT.md and SDD-TEMPLATE.md
2. Create PLAN.md with points 1-N
3. Request human approval before code
4. Generate code by plan points
5. Write tests for 100% of scenarios
6. Verify against original PLAN.md
7. Commit: "Rule[N]: [description]"
```

---

## 📄 License

MIT License - Use freely in your projects
