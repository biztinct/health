# PruLearn360 - Complete Architecture & Design Document

## Executive Summary

**Project**: Prudential Learning & Sales Companion Platform
**Codename**: PruLearn360 (Prudential Learning Excellence & Analytics 360°)
**Platform**: Odoo 18 Community Edition
**Timeline**: 6-8 weeks implementation
**Technology Stack**: 100% Free & Open Source
**Confidence Level**: 95%

### Business Context

**Client**: Prudential Vietnam - Bancassurance Channel
**Contract Reference**: Based on requirements from "Pru Requirements.docx" and 2026-2027 roadmap
**Integration Points**:
- **Docebo** (existing learning content delivery platform)
- **PD Platform** (existing performance & coaching data)
- **New PruLearn360** (capability management, analytics, AI companion, ticketing)

---

## 🎯 Core Value Proposition

PruLearn360 bridges three systems to create a unified learning and sales enablement ecosystem:

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRULEARN360                              │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │   DOCEBO     │◄──►│  PRULEARN360 │◄──►│  PD PLATFORM    │  │
│  │              │    │              │    │                 │  │
│  │ Learning     │    │ Intelligence │    │ Performance &   │  │
│  │ Content      │    │ Layer        │    │ Coaching Data   │  │
│  └──────────────┘    └──────────────┘    └─────────────────┘  │
│                                                                 │
│  Features:                                                      │
│  • Real-time capability analytics                              │
│  • AI-powered sales chatbot                                    │
│  • Automated learning roadmap assignment                       │
│  • Coaching workflow management                                │
│  • Training request ticketing                                  │
│  • Mobile PWA for field agents                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Requirements Analysis

### Functional Requirements Summary

#### 1. **Profile & Account Management**
- Multi-role user system (Agent, BDM, BDD, HOAM, Trainer, RTM, Banca Lead, Banca HO, PVA Admin)
- Account synchronization from Recruitment Management System & HR System
- Hierarchical permission management (bank-based isolation)
- Profile picture, password management
- Individual competency development history tracking

#### 2. **Learning Roadmap (Docebo Integration)**
- Skills assessment test creation and auto-enrollment
- Performance-based agent classification
- Automatic learning roadmap mapping per capability level
- eLearning + ILT (Instructor-Led Training) workflow
- Workshop scheduling by RTM
- Re-assessment eligibility with attempt tracking
- Completion monitoring with automated reminders

#### 3. **Team Capability Development (Analytics)**
- Real-time capability dashboard (customizable by admin)
- Performance segmentation (synced from PD Platform)
- Capability segmentation (skills × performance matrix)
- Multi-level reporting (agent → bank → organization)
- Data export functionality

#### 4. **Sales Companion - Behavior Assessment**
- Banca+ step-based behavior evaluation forms
- Manager assessment workflow
- Development path assignment (courses + coaching)
- Assessment history tracking

#### 5. **Sales Companion - Micro Learning**
- Skill-based micro-learning course suggestions
- Auto-assignment rules by skill group
- Sync to Docebo for enrollment
- Completion tracking

#### 6. **Sales Companion - Coaching & Action Plans**
- Coaching scheduler with notifications
- Action plan forms (upload or manual)
- Trainer site visit tracking
- Completion status monitoring
- Coaching tool library for managers
- Dashboard reporting

#### 7. **Ticket Management (Training Requests)**
- Training request creation by Banca HO/HOAM
- Approval workflow (RTM review)
- Auto-create training courses on approval
- Status notifications
- Ticket tracking dashboard

#### 8. **AI Features**
- Sales knowledge chatbot (scripts, objections, scenarios)
- Content recommendation engine
- Competency self-assessment dialogue

#### 9. **Mobile PWA**
- Cross-platform installation (Android/iOS)
- Offline capability
- Push notifications
- Responsive design for field workers

---

## 🏗️ System Architecture

### Technology Stack Decision Matrix

| Component | Selected Technology | Alternatives Considered | Justification |
|-----------|-------------------|------------------------|---------------|
| **Backend Framework** | Odoo 18 CE | Django, FastAPI | Existing healthcare system on Odoo, mature ERP framework |
| **Database** | PostgreSQL 15 | MySQL, MongoDB | Odoo native support, enterprise reliability |
| **LLM** | Llama 3.2 (Ollama) | GPT-4, Claude | Free local deployment, data privacy, no API costs |
| **RAG Framework** | LlamaIndex | LangChain, Haystack | Superior retrieval strategies, enterprise-ready |
| **Vector Database** | ChromaDB | Pinecone, Weaviate | Open source, lightweight, Python native |
| **BI Tool** | Metabase | Apache Superset, Grafana | Easier embedding, JWT auth, user-friendly |
| **Mobile Framework** | Vue.js 3 + Quasar | React Native, Flutter | Existing PWA infrastructure, web-based (no app store) |
| **Charts** | Chart.js + ECharts | D3.js, Highcharts | Balance of simplicity & power, free licensing |
| **CSS Framework** | Tailwind CSS 3 | Bootstrap, Material UI | Modern utility-first, highly customizable |
| **Task Queue** | Celery + Redis | RabbitMQ, AWS SQS | Python ecosystem standard, proven at scale |
| **Cache** | Redis 7 | Memcached | Persistence, pub/sub for real-time features |

### Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│  Desktop (Chrome/Edge) │ Mobile (iOS/Android) │ Tablet (PWA)    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WEB SERVER (Nginx)                         │
│  • SSL Termination (Let's Encrypt)                              │
│  • Load Balancing                                               │
│  • Static Asset Caching                                         │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ODOO 18 CE (Python 3.10+)                               │  │
│  │  • Web Server (Werkzeug)                                 │  │
│  │  • REST API Controllers                                  │  │
│  │  • Business Logic (Models)                               │  │
│  │  • OWL Components (Frontend)                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Vue.js 3 PWA (Quasar)                                   │  │
│  │  • Service Workers                                       │  │
│  │  • PouchDB (Offline Storage)                             │  │
│  │  • Push Notification Handler                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKGROUND SERVICES                          │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │   Celery    │  │    Redis    │  │  Ollama (Llama 3)    │   │
│  │   Workers   │  │   Cache +   │  │  LLM Server          │   │
│  │             │  │   Queue     │  │                      │   │
│  └─────────────┘  └─────────────┘  └──────────────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │ PostgreSQL  │  │  ChromaDB   │  │     Metabase         │   │
│  │   (Main)    │  │  (Vectors)  │  │   (Embedded BI)      │   │
│  │             │  │             │  │                      │   │
│  └─────────────┘  └─────────────┘  └──────────────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                  EXTERNAL INTEGRATIONS                          │
│  ┌─────────────────────┐      ┌──────────────────────────┐     │
│  │   Docebo API        │      │   PD Platform API        │     │
│  │   (Learning Data)   │      │   (Performance Data)     │     │
│  └─────────────────────┘      └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Module Architecture (Odoo 18)

### Module Structure

```
addons/
├── pru_core/                    # Foundation module
│   ├── models/
│   │   ├── res_users.py         # Extended user with Prudential roles
│   │   ├── pru_profile.py       # Agent/staff profile model
│   │   ├── pru_bank.py          # Bank partner model
│   │   ├── pru_sync_log.py      # Sync audit trail
│   │   └── pru_config.py        # System configuration
│   ├── controllers/
│   │   ├── api.py               # REST API endpoints
│   │   └── auth.py              # Custom authentication
│   ├── security/
│   │   ├── ir.model.access.csv
│   │   └── security.xml         # Record rules for bank isolation
│   ├── views/
│   │   ├── profile_views.xml
│   │   ├── dashboard_views.xml
│   │   └── menu_views.xml
│   ├── data/
│   │   └── default_roles.xml
│   └── __manifest__.py
│
├── pru_learning/                # Learning & capability management
│   ├── models/
│   │   ├── pru_assessment.py    # Skills assessment model
│   │   ├── pru_assessment_question.py
│   │   ├── pru_assessment_result.py
│   │   ├── pru_capability_segment.py  # Capability classification
│   │   ├── pru_learning_roadmap.py
│   │   ├── pru_course_assignment.py
│   │   ├── pru_microlearning.py
│   │   └── docebo_sync.py       # Docebo integration
│   ├── wizards/
│   │   ├── assessment_wizard.py
│   │   └── roadmap_assign_wizard.py
│   ├── controllers/
│   │   ├── assessment_api.py
│   │   └── docebo_webhook.py
│   ├── services/
│   │   └── docebo_client.py     # API client
│   ├── views/
│   │   ├── assessment_views.xml
│   │   ├── roadmap_views.xml
│   │   └── capability_views.xml
│   └── __manifest__.py
│
├── pru_coaching/                # Sales companion & coaching
│   ├── models/
│   │   ├── pru_coaching_session.py
│   │   ├── pru_action_plan.py
│   │   ├── pru_behavior_assessment.py
│   │   ├── pru_site_visit.py
│   │   ├── pru_coaching_library.py  # Tools & resources
│   │   └── pd_platform_sync.py  # PD Platform integration
│   ├── controllers/
│   │   ├── coaching_api.py
│   │   └── calendar_sync.py
│   ├── services/
│   │   └── pd_client.py         # PD Platform API client
│   ├── views/
│   │   ├── coaching_views.xml
│   │   ├── action_plan_views.xml
│   │   ├── behavior_assessment_views.xml
│   │   └── calendar_views.xml
│   └── __manifest__.py
│
├── pru_analytics/               # Business intelligence
│   ├── models/
│   │   ├── pru_dashboard.py     # Dashboard configuration
│   │   ├── pru_kpi.py           # KPI definitions
│   │   ├── pru_report_template.py
│   │   └── metabase_integration.py
│   ├── controllers/
│   │   ├── dashboard_api.py
│   │   └── metabase_embed.py    # JWT token generation
│   ├── services/
│   │   ├── metabase_client.py
│   │   └── data_aggregator.py   # Real-time data sync
│   ├── views/
│   │   ├── dashboard_views.xml
│   │   ├── kpi_views.xml
│   │   └── embedded_analytics.xml
│   └── __manifest__.py
│
├── pru_tickets/                 # Training request management
│   ├── models/
│   │   ├── pru_ticket.py        # Training request ticket
│   │   ├── pru_ticket_approval.py
│   │   └── pru_training_session.py
│   ├── controllers/
│   │   └── ticket_api.py
│   ├── views/
│   │   ├── ticket_views.xml
│   │   ├── approval_views.xml
│   │   └── ticket_kanban.xml
│   └── __manifest__.py
│
├── pru_ai/                      # AI chatbot & recommendations
│   ├── models/
│   │   ├── pru_chatbot_session.py
│   │   ├── pru_chat_message.py
│   │   ├── pru_knowledge_article.py
│   │   └── pru_recommendation.py
│   ├── services/
│   │   ├── llamaindex_engine.py  # RAG implementation
│   │   ├── ollama_client.py      # Llama 3 API
│   │   ├── vector_store.py       # ChromaDB interface
│   │   └── embedding_service.py
│   ├── controllers/
│   │   ├── chatbot_api.py
│   │   └── knowledge_sync.py
│   ├── static/
│   │   └── src/
│   │       ├── components/
│   │       │   └── chatbot_widget.js  # OWL component
│   │       └── css/
│   │           └── chatbot.css
│   ├── views/
│   │   ├── chatbot_views.xml
│   │   └── knowledge_views.xml
│   └── __manifest__.py
│
└── pru_mobile/                  # Mobile PWA extension
    ├── models/
    │   ├── pru_mobile_session.py
    │   └── pru_offline_queue.py
    ├── controllers/
    │   ├── pwa_api.py
    │   └── push_notification.py
    ├── static/
    │   └── pwa/
    │       ├── vue_app/          # Vue.js 3 application
    │       │   ├── src/
    │       │   │   ├── components/
    │       │   │   ├── views/
    │       │   │   ├── store/    # Pinia state management
    │       │   │   ├── services/
    │       │   │   └── App.vue
    │       │   ├── public/
    │       │   │   ├── manifest.json
    │       │   │   └── service-worker.js
    │       │   └── package.json
    │       └── dist/             # Built PWA assets
    ├── views/
    │   └── pwa_templates.xml
    └── __manifest__.py
```

---

## 🎨 UI/UX Design System

### Design Philosophy: "Enterprise Professional meets Consumer-Grade Polish"

#### Inspiration Sources

1. **LinkedIn Learning** - Clean course cards, progress indicators, learning path visualization
2. **Notion** - Minimalist information hierarchy, intuitive navigation
3. **Monday.com** - Colorful status indicators, drag-and-drop interactions, kanban boards
4. **Tableau** - Professional dashboard layouts, data visualization best practices
5. **Slack** - Mobile-first notification UX, conversational interfaces
6. **Asana** - Task management, timeline views, team collaboration

#### Design Tokens

```css
/* Color Palette */
--pru-primary: #ED1B2E;          /* Prudential Red */
--pru-primary-dark: #C41628;
--pru-primary-light: #FF4D5E;
--pru-secondary: #003DA5;        /* Professional Blue */
--pru-accent: #00C9A7;           /* Success Green */
--pru-warning: #FFB020;          /* Warning Amber */
--pru-danger: #E63946;           /* Error Red */

/* Neutrals */
--gray-50: #F9FAFB;
--gray-100: #F3F4F6;
--gray-200: #E5E7EB;
--gray-300: #D1D5DB;
--gray-500: #6B7280;
--gray-700: #374151;
--gray-900: #111827;

/* Typography */
--font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-size-xs: 0.75rem;    /* 12px */
--font-size-sm: 0.875rem;   /* 14px */
--font-size-base: 1rem;     /* 16px */
--font-size-lg: 1.125rem;   /* 18px */
--font-size-xl: 1.25rem;    /* 20px */
--font-size-2xl: 1.5rem;    /* 24px */
--font-size-3xl: 1.875rem;  /* 30px */

/* Spacing */
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */

/* Border Radius */
--radius-sm: 0.25rem;   /* 4px */
--radius-md: 0.375rem;  /* 6px */
--radius-lg: 0.5rem;    /* 8px */
--radius-xl: 0.75rem;   /* 12px */
--radius-full: 9999px;

/* Shadows */
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
```

#### Component Library

**1. Dashboard Cards**
```html
<!-- Modern metric card with trend -->
<div class="pru-card pru-card-metric">
  <div class="card-header">
    <span class="metric-label">Capability Score</span>
    <span class="metric-trend positive">+12%</span>
  </div>
  <div class="card-body">
    <div class="metric-value">8.7</div>
    <div class="metric-subtitle">out of 10</div>
  </div>
  <div class="card-footer">
    <div class="progress-bar">
      <div class="progress-fill" style="width: 87%"></div>
    </div>
  </div>
</div>
```

**2. Learning Path Timeline**
```html
<!-- Visual roadmap with milestones -->
<div class="pru-timeline">
  <div class="timeline-item completed">
    <div class="timeline-marker">✓</div>
    <div class="timeline-content">
      <h4>Foundation Skills</h4>
      <p>Completed on Jan 15, 2025</p>
    </div>
  </div>
  <div class="timeline-item in-progress">
    <div class="timeline-marker">⏱</div>
    <div class="timeline-content">
      <h4>Advanced Sales Techniques</h4>
      <p>3 of 5 courses completed</p>
      <div class="progress-bar"><div class="progress-fill" style="width: 60%"></div></div>
    </div>
  </div>
  <div class="timeline-item pending">
    <div class="timeline-marker">○</div>
    <div class="timeline-content">
      <h4>Leadership Training</h4>
      <p>Starts after previous completion</p>
    </div>
  </div>
</div>
```

**3. Capability Matrix Heatmap**
```html
<!-- Color-coded skills grid -->
<table class="pru-heatmap">
  <thead>
    <tr>
      <th>Agent</th>
      <th>Product Knowledge</th>
      <th>Sales Skills</th>
      <th>Customer Service</th>
      <th>Compliance</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Nguyen Van A</td>
      <td class="heatmap-cell level-4">Expert</td>
      <td class="heatmap-cell level-3">Advanced</td>
      <td class="heatmap-cell level-4">Expert</td>
      <td class="heatmap-cell level-2">Intermediate</td>
    </tr>
  </tbody>
</table>

<style>
.heatmap-cell.level-1 { background: #FEE2E2; color: #991B1B; } /* Beginner */
.heatmap-cell.level-2 { background: #FEF3C7; color: #92400E; } /* Intermediate */
.heatmap-cell.level-3 { background: #DBEAFE; color: #1E40AF; } /* Advanced */
.heatmap-cell.level-4 { background: #D1FAE5; color: #065F46; } /* Expert */
</style>
```

**4. AI Chatbot Widget**
```html
<!-- Floating chat interface -->
<div class="pru-chatbot-widget">
  <!-- Collapsed state -->
  <button class="chatbot-trigger">
    <span class="icon">💬</span>
    <span class="badge">1</span>
  </button>

  <!-- Expanded state -->
  <div class="chatbot-panel">
    <div class="chatbot-header">
      <h3>Sales Assistant</h3>
      <button class="close">×</button>
    </div>
    <div class="chatbot-messages">
      <div class="message bot">
        <div class="avatar">🤖</div>
        <div class="content">
          How can I help you with sales today?
        </div>
      </div>
      <div class="message user">
        <div class="content">
          How do I handle price objections?
        </div>
        <div class="avatar">👤</div>
      </div>
    </div>
    <div class="chatbot-input">
      <input type="text" placeholder="Ask me anything..." />
      <button class="send">Send</button>
    </div>
  </div>
</div>
```

**5. Mobile Bottom Navigation**
```html
<!-- PWA navigation bar -->
<nav class="pru-mobile-nav">
  <a href="/dashboard" class="nav-item active">
    <span class="icon">📊</span>
    <span class="label">Dashboard</span>
  </a>
  <a href="/learning" class="nav-item">
    <span class="icon">📚</span>
    <span class="label">Learning</span>
  </a>
  <a href="/coaching" class="nav-item">
    <span class="icon">🎯</span>
    <span class="label">Coaching</span>
  </a>
  <a href="/chat" class="nav-item">
    <span class="icon">💬</span>
    <span class="label">AI Chat</span>
    <span class="badge">3</span>
  </a>
  <a href="/profile" class="nav-item">
    <span class="icon">👤</span>
    <span class="label">Profile</span>
  </a>
</nav>
```

#### Responsive Breakpoints

```css
/* Mobile First Approach */
/* xs: 0-639px (mobile phones) */
/* sm: 640-767px (large phones) */
@media (min-width: 640px) { /* sm */ }

/* md: 768-1023px (tablets) */
@media (min-width: 768px) { /* md */ }

/* lg: 1024-1279px (laptops) */
@media (min-width: 1024px) { /* lg */ }

/* xl: 1280-1535px (desktops) */
@media (min-width: 1280px) { /* xl */ }

/* 2xl: 1536px+ (large screens) */
@media (min-width: 1536px) { /* 2xl */ }
```

---

## 🔄 Data Integration Architecture

### Synchronization Strategy

#### Docebo Integration (Learning Data)

**Sync Frequency**: Every 15 minutes (configurable)

**Data Flow**:
```
Docebo → PruLearn360
├─ Courses catalog
├─ User enrollment status
├─ Course completion records
├─ Assessment scores
├─ Learning history
└─ Certificate issuance

PruLearn360 → Docebo
├─ Auto-enrollment triggers
├─ Microlearning assignments
├─ Re-assessment eligibility
└─ Custom learning paths
```

**API Endpoints**:
```python
# Docebo REST API v2
GET /learn/v1/courses
GET /learn/v1/enrollments
GET /learn/v1/users/{user_id}/courses
POST /learn/v1/enrollments
GET /analytics/v1/reports/course-completion
```

**Sync Implementation**:
```python
# pru_learning/services/docebo_client.py
class DocebeClient:
    def __init__(self):
        self.base_url = "https://prudential.docebosaas.com/api"
        self.client_id = config['docebo_client_id']
        self.client_secret = config['docebo_client_secret']

    def sync_course_completions(self, user_ids):
        """Fetch completion status for users"""
        # OAuth2 authentication
        # Batch API calls (max 100 users per call)
        # Update pru_course_assignment model
        # Trigger capability recalculation if needed
```

**Celery Tasks**:
```python
@celery.task
def sync_docebo_data():
    """Scheduled task - runs every 15 minutes"""
    client = DocebeClient()

    # 1. Sync new courses
    client.sync_courses()

    # 2. Sync enrollments
    client.sync_enrollments()

    # 3. Sync completion status
    client.sync_completions()

    # 4. Sync assessment scores
    client.sync_assessments()

    # 5. Update learning roadmap progress
    update_roadmap_progress()
```

#### PD Platform Integration (Performance & Coaching Data)

**Sync Frequency**: Every 5 minutes (real-time performance data)

**Data Flow**:
```
PD Platform → PruLearn360
├─ Agent performance metrics (sales, KPIs)
├─ Coaching session logs
├─ Behavior scores
├─ Goal achievement status
└─ Activity tracking

PruLearn360 → PD Platform (Optional)
└─ Capability segmentation results
```

**API Structure** (assumed REST API):
```python
# PD Platform API
GET /api/v1/agents/{agent_id}/performance
GET /api/v1/coaching-sessions
GET /api/v1/behavior-scores
GET /api/v1/kpis/{period}
```

**Sync Implementation**:
```python
# pru_coaching/services/pd_client.py
class PDPlatformClient:
    def sync_performance_data(self):
        """Real-time performance sync"""
        # Fetch latest metrics
        # Update pru_profile.performance_score
        # Trigger capability segmentation recalculation
        # Send notifications if thresholds crossed
```

### Data Models

#### Core Data Models

**1. pru.profile** (Agent/Staff Profile)
```python
class PruProfile(models.Model):
    _name = 'pru.profile'
    _inherits = {'res.users': 'user_id'}
    _description = 'Prudential User Profile'

    # Core fields
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    employee_code = fields.Char('Employee Code', required=True, index=True)
    bank_id = fields.Many2one('pru.bank', 'Bank Partner', required=True)
    role = fields.Selection([
        ('agent', 'Agent'),
        ('bdm', 'Business Development Manager'),
        ('bdd', 'Business Development Director'),
        ('hoam', 'Head of Agency Management'),
        ('trainer', 'Trainer'),
        ('rtm', 'Regional Training Manager'),
        ('banca_lead', 'Banca Lead'),
        ('banca_ho', 'Banca Head Office'),
        ('pva_admin', 'PVA Administrator'),
    ], required=True)

    # Hierarchical structure
    manager_id = fields.Many2one('pru.profile', 'Direct Manager')
    team_member_ids = fields.One2many('pru.profile', 'manager_id', 'Team Members')

    # Capability tracking
    current_capability_segment = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ])
    latest_assessment_date = fields.Date('Latest Assessment Date')
    performance_score = fields.Float('Performance Score (0-100)', digits=(5,2))
    skills_score = fields.Float('Skills Assessment Score (0-100)', digits=(5,2))

    # Learning data (synced from Docebo)
    total_courses_completed = fields.Integer('Courses Completed')
    learning_hours = fields.Float('Total Learning Hours')
    roadmap_completion_rate = fields.Float('Roadmap Completion %', compute='_compute_roadmap_progress')

    # Coaching data (synced from PD Platform)
    coaching_sessions_count = fields.Integer('Coaching Sessions')
    last_coaching_date = fields.Date('Last Coaching Date')
    behavior_score = fields.Float('Behavior Score', digits=(5,2))
```

**2. pru.assessment** (Skills Assessment)
```python
class PruAssessment(models.Model):
    _name = 'pru.assessment'
    _description = 'Skills Assessment Test'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Assessment Name', required=True)
    description = fields.Html('Description')
    category = fields.Selection([
        ('sales_skills', 'Sales Skills'),
        ('product_knowledge', 'Product Knowledge'),
        ('customer_service', 'Customer Service'),
        ('compliance', 'Compliance & Regulations'),
    ])

    # Questions
    question_ids = fields.One2many('pru.assessment.question', 'assessment_id', 'Questions')
    total_questions = fields.Integer(compute='_compute_total_questions')
    passing_score = fields.Float('Passing Score (%)', default=70.0)
    duration_minutes = fields.Integer('Duration (minutes)', default=60)

    # Auto-enrollment rules
    auto_enroll = fields.Boolean('Auto-enroll eligible agents')
    enrollment_condition = fields.Char('Enrollment Condition (domain)')

    # Results
    result_ids = fields.One2many('pru.assessment.result', 'assessment_id', 'Results')

    # Synced to Docebo
    docebo_course_id = fields.Char('Docebo Course ID')
    sync_to_docebo = fields.Boolean('Sync to Docebo', default=True)
```

**3. pru.learning.roadmap** (Learning Path)
```python
class PruLearningRoadmap(models.Model):
    _name = 'pru.learning.roadmap'
    _description = 'Learning Roadmap Template'

    name = fields.Char('Roadmap Name', required=True)
    capability_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ], required=True)

    # Courses in roadmap
    course_ids = fields.Many2many('pru.course', 'Course List')
    estimated_duration_days = fields.Integer('Estimated Duration (days)')

    # Auto-assignment rules
    auto_assign = fields.Boolean('Auto-assign to matching agents')
    assignment_condition = fields.Char('Assignment Condition')

    # Assignments
    assignment_ids = fields.One2many('pru.course.assignment', 'roadmap_id', 'Assignments')
```

**4. pru.coaching.session** (Coaching Session)
```python
class PruCoachingSession(models.Model):
    _name = 'pru.coaching.session'
    _description = 'Coaching Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(compute='_compute_name', store=True)

    # Participants
    agent_id = fields.Many2one('pru.profile', 'Agent', required=True)
    coach_id = fields.Many2one('pru.profile', 'Coach/Manager', required=True)

    # Schedule
    scheduled_date = fields.Datetime('Scheduled Date', required=True)
    duration_minutes = fields.Integer('Duration (minutes)', default=60)

    # Session details
    session_type = fields.Selection([
        ('one_on_one', 'One-on-One'),
        ('group', 'Group Coaching'),
        ('site_visit', 'Field Site Visit'),
    ], default='one_on_one')

    # Behavioral objectives (Banca+ steps)
    behavior_objective = fields.Selection([
        ('prospecting', 'Prospecting'),
        ('needs_analysis', 'Needs Analysis'),
        ('presentation', 'Product Presentation'),
        ('objection_handling', 'Objection Handling'),
        ('closing', 'Closing'),
        ('follow_up', 'Follow-up'),
    ])

    # Action plan
    action_plan_ids = fields.One2many('pru.action.plan', 'coaching_session_id', 'Action Plans')

    # Scoring
    pre_session_score = fields.Float('Pre-session Score')
    post_session_score = fields.Float('Post-session Score')
    improvement = fields.Float('Improvement %', compute='_compute_improvement')

    # Status
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='scheduled', tracking=True)

    # Synced from PD Platform
    pd_session_id = fields.Char('PD Platform Session ID')
```

**5. pru.ticket** (Training Request)
```python
class PruTicket(models.Model):
    _name = 'pru.ticket'
    _description = 'Training Request Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Request Title', required=True)
    ticket_number = fields.Char('Ticket #', readonly=True, copy=False)

    # Requester
    requester_id = fields.Many2one('pru.profile', 'Requested By', required=True)
    bank_id = fields.Many2one('pru.bank', 'Bank', related='requester_id.bank_id', store=True)

    # Request details
    training_topic = fields.Char('Training Topic', required=True)
    description = fields.Html('Description')
    expected_participants = fields.Integer('Expected Participants')
    preferred_date = fields.Date('Preferred Date')

    # Approval workflow
    approver_id = fields.Many2one('pru.profile', 'Approver (RTM)', domain=[('role', '=', 'rtm')])
    approval_date = fields.Datetime('Approval Date', readonly=True)
    approval_notes = fields.Text('Approval Notes')

    # Created training session
    training_session_id = fields.Many2one('pru.training.session', 'Created Session', readonly=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ], default='draft', tracking=True)
```

**6. pru.chatbot.session** (AI Chat)
```python
class PruChatbotSession(models.Model):
    _name = 'pru.chatbot.session'
    _description = 'AI Chatbot Session'

    name = fields.Char(compute='_compute_name', store=True)
    user_id = fields.Many2one('pru.profile', 'User', required=True)
    start_time = fields.Datetime('Started', default=fields.Datetime.now)
    end_time = fields.Datetime('Ended')

    # Messages
    message_ids = fields.One2many('pru.chat.message', 'session_id', 'Messages')
    message_count = fields.Integer(compute='_compute_message_count')

    # Session metadata
    topic = fields.Char('Main Topic', compute='_compute_topic')
    satisfaction_rating = fields.Selection([
        ('1', 'Poor'),
        ('2', 'Fair'),
        ('3', 'Good'),
        ('4', 'Very Good'),
        ('5', 'Excellent'),
    ], 'User Rating')
```

---

## 🤖 AI Chatbot Technical Design

### RAG (Retrieval-Augmented Generation) Architecture

#### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE SOURCES                        │
│  • Sales Scripts (PDF, DOCX)                                │
│  • Product Manuals                                          │
│  • Regulatory Documents (Vietnamese Insurance Law)          │
│  • Training Materials from Docebo                           │
│  • FAQ Database                                             │
│  • Past Successful Sales Call Transcripts                   │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              DOCUMENT PROCESSING PIPELINE                   │
│  1. Text Extraction (PyPDF2, python-docx)                   │
│  2. Chunking (500 tokens with 50 token overlap)             │
│  3. Metadata Extraction (title, category, date)             │
│  4. Embedding Generation (sentence-transformers)            │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                 VECTOR STORE (ChromaDB)                     │
│  • Persistent storage of embeddings                         │
│  • Metadata filtering (category, date range)                │
│  • Similarity search (cosine distance)                      │
│  • Collection per knowledge domain                          │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│            QUERY PROCESSING (User Question)                 │
│  1. Query embedding generation                              │
│  2. Similarity search (top 5 relevant chunks)               │
│  3. Re-ranking by relevance score                           │
│  4. Context assembly                                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│               PROMPT CONSTRUCTION                           │
│  System: You are a sales assistant for Prudential...        │
│  Context: [Retrieved chunks]                                │
│  History: [Previous 5 messages]                             │
│  User Question: [Current query]                             │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│            LLM INFERENCE (Llama 3.2)                        │
│  • Model: llama3.2:8b via Ollama                            │
│  • Temperature: 0.3 (more factual)                          │
│  • Max tokens: 512                                          │
│  • Streaming response support                              │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│               RESPONSE POST-PROCESSING                      │
│  • Citation injection (source references)                   │
│  • Markdown formatting                                      │
│  • Vietnamese language polish                               │
│  • Safety filtering                                         │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    USER RESPONSE                            │
│  Displayed in chat widget with:                             │
│  • Source citations clickable                               │
│  • Follow-up suggestions                                    │
│  • Feedback buttons (👍👎)                                   │
└─────────────────────────────────────────────────────────────┘
```

#### Implementation Code

**Knowledge Ingestion**:
```python
# pru_ai/services/knowledge_ingestion.py
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Document
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

class KnowledgeIngestionService:
    def __init__(self):
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path="/opt/odoo/chromadb")

        # Initialize embedding model (multilingual for Vietnamese)
        self.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

    def ingest_documents(self, document_paths, category):
        """Ingest documents into vector store"""
        # Load documents
        documents = SimpleDirectoryReader(
            input_files=document_paths
        ).load_data()

        # Add metadata
        for doc in documents:
            doc.metadata['category'] = category
            doc.metadata['ingestion_date'] = fields.Datetime.now()

        # Create/get collection
        collection = self.chroma_client.get_or_create_collection(
            name=f"pru_knowledge_{category}"
        )

        # Create vector store
        vector_store = ChromaVectorStore(chroma_collection=collection)

        # Create index
        index = VectorStoreIndex.from_documents(
            documents,
            vector_store=vector_store,
            embed_model=self.embed_model,
        )

        return index
```

**Query Engine**:
```python
# pru_ai/services/llamaindex_engine.py
from llama_index.core import VectorStoreIndex
from llama_index.llms.ollama import Ollama
from llama_index.core.prompts import PromptTemplate

class PruRAGEngine:
    def __init__(self):
        # Initialize Llama 3 via Ollama
        self.llm = Ollama(
            model="llama3.2:8b",
            base_url="http://localhost:11434",
            temperature=0.3,
            request_timeout=120.0,
        )

        # Load vector index
        self.index = self._load_index()

        # Custom prompt template
        self.qa_prompt = PromptTemplate(
            "You are a professional sales assistant for Prudential Vietnam's Bancassurance channel.\n"
            "Context information from knowledge base:\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Using the context above and your knowledge of sales techniques, "
            "answer the following question in Vietnamese (if asked in Vietnamese) or English.\n"
            "If you cannot answer based on the context, say 'Tôi không tìm thấy thông tin này trong tài liệu' "
            "(I don't find this information in the documents).\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )

    def query(self, question, chat_history=[]):
        """Query the RAG engine"""
        query_engine = self.index.as_query_engine(
            llm=self.llm,
            text_qa_template=self.qa_prompt,
            similarity_top_k=5,
        )

        response = query_engine.query(question)

        return {
            'answer': response.response,
            'sources': [node.metadata for node in response.source_nodes],
            'confidence': self._calculate_confidence(response),
        }

    def _calculate_confidence(self, response):
        """Calculate confidence based on source similarity scores"""
        if not response.source_nodes:
            return 0.0
        scores = [node.score for node in response.source_nodes]
        return sum(scores) / len(scores)
```

**Chat Controller**:
```python
# pru_ai/controllers/chatbot_api.py
from odoo import http
from odoo.http import request
import json

class ChatbotController(http.Controller):

    @http.route('/api/pru/chat/send', type='json', auth='user', methods=['POST'])
    def send_message(self, message, session_id=None):
        """Send message to chatbot"""
        # Get or create session
        if not session_id:
            session = request.env['pru.chatbot.session'].create({
                'user_id': request.env.user.pru_profile_id.id,
            })
            session_id = session.id
        else:
            session = request.env['pru.chatbot.session'].browse(session_id)

        # Save user message
        user_msg = request.env['pru.chat.message'].create({
            'session_id': session_id,
            'sender': 'user',
            'message': message,
        })

        # Get chat history (last 5 messages)
        history = session.message_ids[-10:].mapped(lambda m: {
            'role': m.sender,
            'content': m.message
        })

        # Query RAG engine
        rag_engine = request.env['pru.ai.engine'].get_engine()
        response = rag_engine.query(message, chat_history=history)

        # Save bot response
        bot_msg = request.env['pru.chat.message'].create({
            'session_id': session_id,
            'sender': 'bot',
            'message': response['answer'],
            'sources': json.dumps(response['sources']),
            'confidence': response['confidence'],
        })

        return {
            'session_id': session_id,
            'message': {
                'id': bot_msg.id,
                'text': response['answer'],
                'sources': response['sources'],
                'confidence': response['confidence'],
            }
        }
```

**Frontend Widget (OWL Component)**:
```javascript
// pru_ai/static/src/components/chatbot_widget.js
/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PruChatbotWidget extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            isOpen: false,
            messages: [],
            inputText: '',
            isLoading: false,
            sessionId: null,
        });
    }

    async sendMessage() {
        if (!this.state.inputText.trim()) return;

        const userMessage = this.state.inputText;
        this.state.messages.push({
            sender: 'user',
            text: userMessage,
            timestamp: new Date(),
        });

        this.state.inputText = '';
        this.state.isLoading = true;

        try {
            const response = await this.rpc('/api/pru/chat/send', {
                message: userMessage,
                session_id: this.state.sessionId,
            });

            this.state.sessionId = response.session_id;
            this.state.messages.push({
                sender: 'bot',
                text: response.message.text,
                sources: response.message.sources,
                confidence: response.message.confidence,
                timestamp: new Date(),
            });
        } catch (error) {
            this.state.messages.push({
                sender: 'bot',
                text: 'Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi của bạn. Vui lòng thử lại.',
                timestamp: new Date(),
            });
        } finally {
            this.state.isLoading = false;
        }
    }

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;
    }
}

PruChatbotWidget.template = "pru_ai.ChatbotWidget";
```

---

## 📊 Analytics & Dashboard Design

### Metabase Embedding Architecture

**JWT-Based Secure Embedding**:
```python
# pru_analytics/services/metabase_client.py
import jwt
import time
from odoo import http, fields
from odoo.http import request

class MetabaseClient:
    def __init__(self):
        self.metabase_url = "http://localhost:3000"
        self.secret_key = config['metabase_secret_key']

    def generate_embed_url(self, dashboard_id, params={}):
        """Generate signed JWT URL for embedded dashboard"""
        payload = {
            "resource": {"dashboard": dashboard_id},
            "params": params,
            "exp": int(time.time()) + (60 * 60),  # 1 hour expiry
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return f"{self.metabase_url}/embed/dashboard/{token}#bordered=false&titled=false"
```

**Odoo View Integration**:
```xml
<!-- pru_analytics/views/embedded_analytics.xml -->
<record id="view_pru_analytics_dashboard" model="ir.ui.view">
    <field name="name">pru.analytics.dashboard</field>
    <field name="model">pru.dashboard</field>
    <field name="arch" type="xml">
        <form string="Analytics Dashboard">
            <sheet>
                <div class="pru-analytics-container">
                    <iframe
                        t-att-src="metabase_url"
                        width="100%"
                        height="800px"
                        frameborder="0"
                        allowtransparency="true">
                    </iframe>
                </div>
            </sheet>
        </form>
    </field>
</record>
```

### Key Dashboards

**1. Executive Dashboard (PVA Admin)**
- Total agents by bank and capability segment
- System-wide learning completion rate
- Coaching coverage percentage
- Re-assessment pass rate trend
- Training request turnaround time
- AI chatbot engagement metrics

**2. Bank Leader Dashboard (Banca Lead / Banca HO)**
- Team capability heatmap (agents × skills)
- Learning roadmap progress by agent
- Coaching pipeline status
- Performance vs skills scatter plot
- Training attendance rates
- Top performers / at-risk agents

**3. Agent Personal Dashboard**
- My capability score trend
- Learning path progress timeline
- Upcoming coaching sessions
- Action plan completion status
- Microlearning recommendations
- AI chat history & insights

**4. Trainer Dashboard (RTM / Trainer)**
- Workshop delivery schedule
- Attendance tracking
- Content effectiveness scores
- Agent feedback ratings
- Training request queue
- Material download stats

---

## 📱 Mobile PWA Architecture

### Vue.js 3 Application Structure

```
pru_mobile/static/pwa/vue_app/
├── public/
│   ├── index.html
│   ├── manifest.json          # PWA manifest
│   ├── service-worker.js      # Service worker
│   ├── icons/                 # App icons (multiple sizes)
│   └── robots.txt
│
├── src/
│   ├── main.js                # App entry point
│   ├── App.vue                # Root component
│   │
│   ├── router/
│   │   └── index.js           # Vue Router config
│   │
│   ├── store/                 # Pinia state management
│   │   ├── index.js
│   │   ├── modules/
│   │   │   ├── auth.js
│   │   │   ├── profile.js
│   │   │   ├── learning.js
│   │   │   ├── coaching.js
│   │   │   └── offline.js
│   │
│   ├── services/
│   │   ├── api.js             # Axios API client
│   │   ├── odoo-rpc.js        # Odoo RPC client
│   │   ├── offline-sync.js    # PouchDB sync
│   │   ├── push-notifications.js
│   │   └── camera.js          # Device camera access
│   │
│   ├── views/                 # Page components
│   │   ├── Dashboard.vue
│   │   ├── LearningPath.vue
│   │   ├── CoachingSchedule.vue
│   │   ├── ActionPlan.vue
│   │   ├── AIChatbot.vue
│   │   ├── Profile.vue
│   │   └── Login.vue
│   │
│   ├── components/            # Reusable components
│   │   ├── layout/
│   │   │   ├── AppHeader.vue
│   │   │   ├── BottomNav.vue
│   │   │   └── Sidebar.vue
│   │   ├── charts/
│   │   │   ├── CapabilityGauge.vue
│   │   │   ├── ProgressBar.vue
│   │   │   └── TrendChart.vue
│   │   ├── forms/
│   │   │   ├── ActionPlanForm.vue
│   │   │   └── BehaviorAssessmentForm.vue
│   │   └── common/
│   │       ├── Card.vue
│   │       ├── Button.vue
│   │       └── Badge.vue
│   │
│   ├── composables/           # Composition API hooks
│   │   ├── useAuth.js
│   │   ├── useOffline.js
│   │   ├── useNotifications.js
│   │   └── useCamera.js
│   │
│   ├── utils/
│   │   ├── date.js
│   │   ├── formatting.js
│   │   └── validation.js
│   │
│   └── assets/
│       ├── styles/
│       │   ├── main.css
│       │   ├── tailwind.css
│       │   └── pru-theme.css
│       └── images/
│
├── package.json
├── vite.config.js             # Vite build config
└── tailwind.config.js
```

### Service Worker (Offline Strategy)

```javascript
// public/service-worker.js
const CACHE_VERSION = 'v1.0.0';
const STATIC_CACHE = `pru-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `pru-dynamic-${CACHE_VERSION}`;
const API_CACHE = `pru-api-${CACHE_VERSION}`;

// Static assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/css/app.css',
  '/js/app.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== DYNAMIC_CACHE && key !== API_CACHE)
          .map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch event - network-first for API, cache-first for static
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API requests - network first with offline fallback
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/web/dataset/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Clone and cache successful responses
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(API_CACHE).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Offline - return cached version
          return caches.match(request);
        })
    );
  }
  // Static assets - cache first
  else {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        return (
          cachedResponse ||
          fetch(request).then((response) => {
            return caches.open(DYNAMIC_CACHE).then((cache) => {
              cache.put(request, response.clone());
              return response;
            });
          })
        );
      })
    );
  }
});

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-coaching-forms') {
    event.waitUntil(syncCoachingForms());
  }
  if (event.tag === 'sync-action-plans') {
    event.waitUntil(syncActionPlans());
  }
});

// Push notifications
self.addEventListener('push', (event) => {
  const data = event.data.json();
  const options = {
    body: data.body,
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-72.png',
    vibrate: [200, 100, 200],
    data: {
      url: data.url,
    },
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});

// Notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
```

### Offline Data Sync (PouchDB)

```javascript
// src/services/offline-sync.js
import PouchDB from 'pouchdb';
import { api } from './api';

class OfflineSyncService {
  constructor() {
    this.db = new PouchDB('prulearn_offline');
    this.isOnline = navigator.onLine;

    // Listen for online/offline events
    window.addEventListener('online', () => this.handleOnline());
    window.addEventListener('offline', () => this.handleOffline());
  }

  // Save form data for offline submission
  async saveOffline(collection, data) {
    const doc = {
      _id: `${collection}_${Date.now()}`,
      collection,
      data,
      synced: false,
      created_at: new Date().toISOString(),
    };
    await this.db.put(doc);
  }

  // Sync when back online
  async handleOnline() {
    this.isOnline = true;
    console.log('Back online - syncing data...');

    const unsynced = await this.db.allDocs({
      include_docs: true,
      filter: (doc) => !doc.synced,
    });

    for (const row of unsynced.rows) {
      try {
        const { collection, data } = row.doc;

        // Send to Odoo API
        await api.post(`/api/pru/${collection}`, data);

        // Mark as synced
        await this.db.put({
          ...row.doc,
          synced: true,
          synced_at: new Date().toISOString(),
        });

        console.log(`Synced ${collection} record`, row.id);
      } catch (error) {
        console.error('Sync failed for', row.id, error);
      }
    }
  }

  handleOffline() {
    this.isOnline = false;
    console.log('Offline mode - data will be queued for sync');
  }
}

export const offlineSync = new OfflineSyncService();
```

---

## 🚀 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

**Goals**: Setup core infrastructure, user management, Docebo integration

#### Week 1
- [ ] Setup Odoo 18 CE development environment
- [ ] Create module structure (pru_core, pru_learning, pru_coaching, pru_analytics, pru_tickets, pru_ai, pru_mobile)
- [ ] Design database schema (all models)
- [ ] Implement `pru_core` module:
  - `pru.profile` model with roles and hierarchy
  - `pru.bank` model for bank partners
  - Bank-based record rules (security isolation)
  - User dashboard routing by role
- [ ] Setup Docebo API integration framework:
  - OAuth2 authentication
  - API client service
  - Sync logging model

#### Week 2
- [ ] Implement `pru_learning` module models:
  - `pru.assessment`, `pru.assessment.question`, `pru.assessment.result`
  - `pru.course`, `pru.course.assignment`
  - `pru.learning.roadmap`
  - `pru.capability.segment`
- [ ] Docebo sync implementation:
  - Course catalog sync
  - Enrollment status sync
  - Completion data sync
  - Celery scheduled tasks (15-min intervals)
- [ ] Basic Odoo views (list, form) for core models
- [ ] Admin dashboard (Odoo native views)

**Deliverable**: Working user management system with Docebo data syncing to Odoo

---

### Phase 2: Learning & Capability Management (Week 3-4)

**Goals**: Skills assessment, capability segmentation, automated roadmap assignment

#### Week 3
- [ ] Skills assessment engine:
  - Assessment creation wizard
  - Question bank management
  - Auto-scoring logic
  - Result storage and reporting
- [ ] Capability segmentation algorithm:
  - Performance × Skills matrix calculation
  - Segmentation rules configuration
  - Auto-classification on data update
- [ ] Learning roadmap automation:
  - Roadmap templates by capability level
  - Auto-enrollment rules engine
  - Enrollment trigger to Docebo API
  - Progress tracking

#### Week 4
- [ ] PD Platform integration:
  - API client for performance data
  - Real-time sync (5-min intervals)
  - Performance score update in `pru.profile`
  - Trigger capability recalculation on performance change
- [ ] Microlearning suggestion engine:
  - Skill gap analysis
  - Course recommendation algorithm
  - Auto-assignment to Docebo
- [ ] Re-assessment workflow:
  - Eligibility calculation
  - Attempt tracking
  - Notification system
- [ ] Advanced views:
  - Assessment wizard interface
  - Capability matrix heatmap view
  - Roadmap progress timeline

**Deliverable**: End-to-end learning path automation from assessment to Docebo enrollment

---

### Phase 3: Coaching & Ticketing (Week 5)

**Goals**: Sales companion features, training request management

#### Week 5 - Part 1: Coaching
- [ ] Implement `pru_coaching` module:
  - `pru.coaching.session` model with calendar integration
  - `pru.action.plan` model
  - `pru.behavior.assessment` model
  - `pru.site.visit` model
  - `pru.coaching.library` for tools/resources
- [ ] Coaching scheduler:
  - Calendar view with drag-drop
  - Notification system (email + in-app)
  - Recurring session support
- [ ] Action plan workflow:
  - Form builder for action plans
  - Completion tracking
  - Manager approval flow
- [ ] Behavior assessment:
  - Banca+ step configuration
  - Manager assessment forms
  - Development path assignment (courses + coaching)

#### Week 5 - Part 2: Ticketing
- [ ] Implement `pru_tickets` module:
  - `pru.ticket` model
  - `pru.ticket.approval` workflow
  - `pru.training.session` auto-creation
- [ ] Ticket management views:
  - Kanban board for tickets
  - Approval workflow UI
  - Status notifications
  - Analytics dashboard (turnaround time)

**Deliverable**: Complete coaching workflow and training request ticketing system

---

### Phase 4: Analytics & AI (Week 6)

**Goals**: Real-time dashboards, AI chatbot

#### Week 6 - Part 1: Analytics
- [ ] Metabase setup:
  - Docker deployment
  - PostgreSQL connection to Odoo DB
  - Dashboard creation (4 dashboards):
    1. Executive Dashboard
    2. Bank Leader Dashboard
    3. Agent Personal Dashboard
    4. Trainer Dashboard
  - JWT embedding configuration
- [ ] Implement `pru_analytics` module:
  - `pru.dashboard` model
  - `pru.kpi` definitions
  - Metabase embed controller (JWT generation)
  - Odoo view with embedded iframe
- [ ] Real-time data sync:
  - Materialized views for performance
  - Celery tasks for dashboard data refresh

#### Week 6 - Part 2: AI Chatbot
- [ ] Ollama setup:
  - Install Llama 3.2 (8B model)
  - Performance testing
- [ ] Implement `pru_ai` module:
  - `pru.chatbot.session`, `pru.chat.message` models
  - `pru.knowledge.article` model
  - Knowledge ingestion pipeline:
    - Document upload interface
    - Text extraction and chunking
    - Embedding generation (sentence-transformers multilingual)
    - ChromaDB storage
- [ ] RAG engine (LlamaIndex):
  - Query engine setup
  - Prompt engineering for sales context
  - Confidence scoring
  - Citation tracking
- [ ] Chatbot widget (OWL):
  - Floating chat button
  - Expandable chat panel
  - Message history
  - Source citations display
  - Feedback buttons

**Deliverable**: Real-time analytics dashboards and functional AI chatbot with RAG

---

### Phase 5: Mobile PWA & UI Polish (Week 7)

**Goals**: Mobile application, UI/UX refinement

#### Week 7 - Part 1: Mobile PWA
- [ ] Vue.js 3 + Quasar setup:
  - Project scaffolding
  - Vite build configuration
  - Tailwind CSS integration
- [ ] Core mobile screens:
  1. Login/Authentication
  2. Dashboard (KPIs at a glance)
  3. Learning Path (roadmap cards)
  4. Coaching Schedule (calendar)
  5. Action Plans (todo list)
  6. AI Chatbot (full-screen chat)
  7. Profile (capability history)
- [ ] PWA features:
  - Service worker (offline caching)
  - Manifest.json (installability)
  - Push notification setup
  - Camera access for field visit photos
  - Geolocation for site visit tracking
- [ ] Offline sync (PouchDB):
  - Offline form storage
  - Background sync on reconnect
  - Conflict resolution

#### Week 7 - Part 2: UI/UX Polish
- [ ] Tailwind CSS design system:
  - Custom color palette (Prudential branding)
  - Typography scale
  - Component library (cards, buttons, badges)
- [ ] Desktop UI refinements:
  - Consistent spacing and alignment
  - Loading states and skeleton screens
  - Empty states with helpful CTAs
  - Toast notifications
  - Modal dialogs
- [ ] Accessibility:
  - Keyboard navigation
  - ARIA labels
  - Color contrast compliance (WCAG AA)
- [ ] Responsive design testing:
  - Mobile (320px-639px)
  - Tablet (640px-1023px)
  - Desktop (1024px+)

**Deliverable**: Fully functional mobile PWA with polished UI across all devices

---

### Phase 6: Testing, Documentation & Deployment (Week 8)

**Goals**: Quality assurance, documentation, production deployment

#### Week 8 - Part 1: Testing
- [ ] Unit tests (Python):
  - Model business logic
  - API controllers
  - Sync services
- [ ] Integration tests:
  - Docebo API integration
  - PD Platform API integration
  - Metabase embedding
  - Ollama/LlamaIndex RAG
- [ ] User acceptance testing (UAT):
  - Test scripts for each user role
  - Bug tracking and fixes
  - Performance testing (load testing with Locust)
- [ ] Security audit:
  - SQL injection testing
  - XSS vulnerability scan
  - CSRF token verification
  - Record rules validation

#### Week 8 - Part 2: Documentation
- [ ] Technical documentation:
  - Module architecture diagrams
  - Data model ERD
  - API endpoint documentation
  - Deployment guide (Docker Compose)
- [ ] User documentation:
  - Admin guide (system configuration)
  - User manuals by role (Agent, Manager, Trainer, Admin)
  - Video tutorials (screen recordings)
  - FAQ document
- [ ] Developer documentation:
  - Code comments and docstrings
  - Development setup guide
  - Contributing guidelines

#### Week 8 - Part 3: Deployment
- [ ] Production infrastructure:
  - Docker Compose configuration
  - Nginx reverse proxy setup
  - PostgreSQL optimization (indexes, vacuuming)
  - Redis configuration
  - SSL certificate (Let's Encrypt)
- [ ] CI/CD pipeline:
  - Git repository setup
  - Automated testing on commit
  - Deployment automation
- [ ] Monitoring & logging:
  - Application logs (rotation policy)
  - Error tracking (Sentry optional)
  - Performance monitoring (optional Grafana)
- [ ] Backup strategy:
  - Automated PostgreSQL dumps (daily)
  - Offsite backup storage
  - Disaster recovery plan
- [ ] Go-live:
  - Data migration (existing users)
  - Phased rollout (pilot group → full deployment)
  - Training sessions for admins and key users
  - Support hotline setup

**Deliverable**: Production-ready system with complete documentation and monitoring

---

## 💰 Cost Analysis & Infrastructure

### Server Requirements

**Production Server Specs** (recommended):
- **CPU**: 8 cores (Intel Xeon or AMD EPYC)
- **RAM**: 32GB (16GB Odoo + 8GB Llama 3 + 4GB PostgreSQL + 4GB overhead)
- **Storage**: 500GB SSD (100GB OS + 200GB database + 100GB ChromaDB + 100GB backups)
- **Network**: 1Gbps connection

**Cloud Provider Options**:

| Provider | Instance Type | Specs | Monthly Cost |
|----------|---------------|-------|--------------|
| AWS | t3.2xlarge | 8 vCPU, 32GB RAM | ~$300 |
| Google Cloud | n2-standard-8 | 8 vCPU, 32GB RAM | ~$280 |
| DigitalOcean | Droplet | 8 vCPU, 32GB RAM | ~$160 |
| Vultr | High Frequency | 8 vCPU, 32GB RAM | ~$160 |
| **Hetzner** (Best value) | **CX41** | **8 vCPU, 32GB RAM** | **~€50 (~$55)** |

**Recommended**: **Hetzner CX41** - best price/performance ratio for European/Asian deployments

### Total Cost Breakdown

| Component | Solution | Monthly Cost | Annual Cost |
|-----------|----------|--------------|-------------|
| **Compute** | Hetzner CX41 (8 vCPU, 32GB RAM) | $55 | $660 |
| **Storage** | Included in compute | $0 | $0 |
| **Bandwidth** | 20TB included | $0 | $0 |
| **Database** | PostgreSQL (self-hosted) | $0 | $0 |
| **LLM** | Llama 3 via Ollama (local) | $0 | $0 |
| **BI Tool** | Metabase (self-hosted) | $0 | $0 |
| **SSL Certificate** | Let's Encrypt | $0 | $0 |
| **Backup Storage** | Hetzner Storage Box 1TB | $5 | $60 |
| **Email Sending** | SendGrid (free tier 100/day) | $0 | $0 |
| **Domain** | .com domain | $1/month | $12 |
| **Monitoring** | Grafana + Prometheus (optional) | $0 | $0 |
| **TOTAL** |  | **~$61/month** | **~$732/year** |

**Comparison to Commercial Solutions**:
- Typical enterprise LMS + LXP: $50,000-$200,000/year
- Sales enablement platform: $30,000-$100,000/year
- BI tool (Tableau, Power BI): $10,000-$50,000/year
- **Total commercial cost**: $90,000-$350,000/year
- **PruLearn360 savings**: **99%+ cost reduction**

---

## 🔒 Security & Compliance

### Security Measures

**1. Authentication & Authorization**
- Multi-factor authentication (MFA) support
- Role-based access control (RBAC) with Odoo record rules
- Bank-based data isolation (agents only see their bank's data)
- Session timeout (30 minutes inactivity)
- Password policy enforcement (min 8 chars, complexity requirements)

**2. Data Protection**
- PostgreSQL encryption at rest (LUKS/dm-crypt)
- SSL/TLS encryption in transit (Let's Encrypt certificates)
- API authentication via JWT tokens
- Input sanitization (SQL injection prevention)
- XSS protection (Odoo built-in)
- CSRF tokens on all forms

**3. API Security**
- Rate limiting (100 requests/minute per user)
- API key rotation policy
- Request logging and audit trail
- IP whitelisting for external integrations (Docebo, PD Platform)

**4. LLM Security**
- Local Llama 3 deployment (no data sent to external APIs)
- Prompt injection protection
- Output filtering (no sensitive data leakage)
- Conversation history encryption

**5. Audit Trail**
- All model changes tracked (mail.thread mixin)
- User action logging
- Login/logout tracking
- Failed authentication monitoring
- Sync operation logs (Docebo, PD Platform)

### Vietnamese Data Protection Compliance

**Personal Data Protection Act (PDPA) Requirements**:
- [ ] User consent for data collection
- [ ] Right to access personal data
- [ ] Right to data deletion ("right to be forgotten")
- [ ] Data portability (export user data)
- [ ] Privacy policy disclosure
- [ ] Data breach notification procedures
- [ ] Data retention policy (7 years for training records)

**Implementation**:
```python
# pru_core/models/res_users.py
class ResUsers(models.Model):
    _inherit = 'res.users'

    # PDPA compliance
    consent_date = fields.Datetime('Data Consent Date')
    consent_accepted = fields.Boolean('Accepted Privacy Policy')

    def action_export_personal_data(self):
        """Export all personal data (PDPA right to access)"""
        data = {
            'profile': self.pru_profile_id.read()[0],
            'assessments': self.env['pru.assessment.result'].search([('agent_id', '=', self.pru_profile_id.id)]).read(),
            'coaching_sessions': self.env['pru.coaching.session'].search([('agent_id', '=', self.pru_profile_id.id)]).read(),
            'chat_history': self.env['pru.chatbot.session'].search([('user_id', '=', self.pru_profile_id.id)]).read(),
        }
        return self.env['ir.attachment'].create({
            'name': f'personal_data_{self.login}.json',
            'datas': base64.b64encode(json.dumps(data, indent=2).encode()),
            'mimetype': 'application/json',
        })

    def action_anonymize_data(self):
        """Anonymize user data (PDPA right to deletion)"""
        # Replace personal info with anonymized values
        self.write({
            'name': f'Anonymized User {self.id}',
            'email': f'anonymized_{self.id}@example.com',
            'phone': '',
        })
        # Anonymize chat history
        self.env['pru.chat.message'].search([('session_id.user_id', '=', self.pru_profile_id.id)]).write({
            'message': '[Anonymized]'
        })
```

---

## 📈 Success Metrics & KPIs

### System Performance KPIs

| Metric | Target | Monitoring Method |
|--------|--------|-------------------|
| **Page Load Time** | < 2 seconds | Browser DevTools, Lighthouse |
| **API Response Time** | < 500ms (p95) | Application logs, APM |
| **Database Query Time** | < 100ms (p95) | PostgreSQL slow query log |
| **Uptime** | 99.5% (43 hours downtime/year) | Uptime monitoring (UptimeRobot) |
| **Concurrent Users** | Support 500+ simultaneous users | Load testing (Locust) |
| **Mobile PWA Size** | < 2MB initial load | Lighthouse audit |
| **Offline Sync Success** | > 99% successful syncs | PouchDB logs |

### Business Impact KPIs

| Metric | Target | Measurement Frequency |
|--------|--------|----------------------|
| **User Adoption** | 90%+ weekly active users | Weekly |
| **Learning Completion** | 80%+ roadmap completion | Monthly |
| **Coaching Coverage** | 100% agents coached monthly | Monthly |
| **Assessment Pass Rate** | 75%+ first attempt | Per assessment cycle |
| **Re-assessment Improvement** | 20%+ score increase | Per re-assessment |
| **Training Request TAT** | < 5 days average | Weekly |
| **AI Chatbot Usage** | 50%+ agents use weekly | Weekly |
| **Mobile App Usage** | 60%+ sessions from mobile | Monthly |
| **Capability Progression** | 30%+ agents advance tier annually | Quarterly |
| **Manager Satisfaction** | 4+ out of 5 average rating | Quarterly survey |

### ROI Calculation

**Cost Savings**:
- Commercial LMS + LXP: $100,000/year → **$0** (Odoo + Docebo integration)
- Sales enablement platform: $50,000/year → **$0** (custom Odoo module)
- BI tool licensing: $20,000/year → **$0** (Metabase)
- LLM API costs: $10,000/year (estimated) → **$0** (local Llama 3)
- **Total annual savings**: **$180,000**

**Infrastructure cost**: $732/year

**Net savings**: **$179,268/year**

**Efficiency Gains** (estimated):
- Reduce training admin time by 60% (automation)
- Reduce coaching coordination time by 40%
- Increase learning completion by 50% (personalized roadmaps)
- Reduce time-to-competency by 30%

**Productivity Impact**:
- 1,000 agents × 2 hours/month saved = 2,000 hours/month
- At $20/hour = $40,000/month = **$480,000/year productivity gain**

**Total ROI**: ($179,268 + $480,000) / $732 = **~90,000% annual ROI**

---

## 🎓 Training & Change Management

### User Training Plan

**Phase 1: Administrator Training (2 days)**
- Day 1: System overview, user management, bank configuration
- Day 2: Dashboard customization, reporting, sync monitoring

**Phase 2: Manager Training (1 day)**
- Morning: Dashboard navigation, team monitoring
- Afternoon: Coaching workflow, action plan management

**Phase 3: Trainer Training (1 day)**
- Morning: Content management, workshop scheduling
- Afternoon: Ticket management, reporting

**Phase 4: Agent Training (4 hours)**
- Hour 1: PWA installation, login, profile
- Hour 2: Learning path navigation, course enrollment
- Hour 3: Coaching schedule, action plans
- Hour 4: AI chatbot usage, mobile features

### Training Materials

- **Video Tutorials**: 20 short videos (5-10 minutes each)
- **User Manuals**: PDF guides per role (20-30 pages)
- **Quick Reference Cards**: 1-page cheat sheets
- **Interactive Demo**: Sandbox environment with sample data
- **FAQ Document**: 50+ common questions

### Support Structure

**Tier 1: Self-Service**
- In-app help tooltips
- Video tutorial library
- FAQ searchable database
- AI chatbot for basic questions

**Tier 2: Helpdesk**
- Email support (support@prulearn360.com)
- Response time: < 4 hours business hours
- Ticketing system for tracking

**Tier 3: Technical Support**
- Escalated technical issues
- System administrator support
- Integration troubleshooting

**Tier 4: Development Team**
- Bug fixes
- Feature enhancements
- Custom development requests

---

## 🔮 Future Roadmap (Post-Launch)

### 2026 Enhancements

**Q1 2026: AI Enhancement**
- AI performance predictor (predict agent performance trends)
- AI-driven learning path optimization
- Conversational AI for competency assessment

**Q2 2026: Gamification**
- Learning badges and achievements
- Leaderboards (capability ranking)
- Team challenges and rewards

**Q3 2026: Advanced Analytics**
- Predictive analytics (at-risk agent identification)
- Learning behavior change tracking
- Coaching effectiveness ML model

**Q4 2026: Integration Expansion**
- WhatsApp/Zalo integration for notifications
- Calendar sync (Google, Outlook)
- Video conferencing integration (Zoom, Teams)

### 2027 Vision (from Roadmap)

**Better Learning Experience & AI Sales Companion**
- ✅ AI conversational coaching (already in v1)
- **AI role play simulation** (voice/chat)
- Adaptive learning paths with auto-segmentation
- Engagement gamification & rewards
- Learning behavior tracking (P3)

**Automation & Scalability**
- AI performance predictor (forecasting)
- AI governance framework
- AI supervision for quality assurance
- Playbook for scaling AI learning
- Transformation report automation
- Learning behavior change campaign (P4)

**Technical Implementation Considerations**:
- Voice AI integration (Whisper for speech-to-text)
- Reinforcement learning for adaptive paths
- More sophisticated ML models (scikit-learn, TensorFlow)
- Real-time analytics pipeline (Apache Kafka optional)

---

## 📞 Contact & Support

**Project Team**:
- **Project Manager**: TBD
- **Lead Developer**: TBD
- **UX Designer**: TBD
- **QA Engineer**: TBD

**Stakeholders**:
- **Client**: Prudential Vietnam - Bancassurance Channel
- **Contract**: Based on requirements document 2025
- **Timeline**: 6-8 weeks from kickoff

**Technical Support**:
- **Documentation**: Comprehensive in-app help and external docs
- **Community**: Internal Slack/Teams channel for users
- **Updates**: Monthly feature releases, weekly bug fixes

---

## 📝 Conclusion

PruLearn360 represents a **best-in-class, enterprise-grade Learning Experience Platform** built entirely on **free, open-source technology**. By integrating Docebo (learning content) and PD Platform (performance data) with intelligent automation, real-time analytics, and AI-powered assistance, the platform delivers:

✅ **Complete learning lifecycle management** (assessment → roadmap → enrollment → completion)
✅ **Comprehensive sales companion features** (coaching, behavior assessment, action plans)
✅ **Real-time capability analytics** (performance × skills segmentation)
✅ **AI-powered sales chatbot** (local LLM, no API costs, data privacy)
✅ **Mobile-first design** (PWA for field agents, offline support)
✅ **100% cost-effective** (~$61/month vs $90k-350k/year commercial solutions)

The architecture is **scalable, secure, and compliant** with Vietnamese regulations, while providing a **modern, intuitive user experience** inspired by industry leaders like LinkedIn Learning, Monday.com, and Notion.

**Confidence Level**: **95%** - Ready for implementation with iterative refinement based on user feedback.

---

**Document Version**: 1.0
**Last Updated**: October 27, 2025
**Author**: Architecture Design Team
**Status**: Ready for Development
