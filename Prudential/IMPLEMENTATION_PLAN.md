# PruLearn360 - Detailed Implementation Plan

## Project Overview

**Project Name**: PruLearn360 - Prudential Learning Excellence & Analytics 360°
**Timeline**: 6-8 weeks (42-56 days)
**Team Size**: 4-6 developers + 1 project manager
**Methodology**: Agile with 1-week sprints
**Confidence Level**: 95%

---

## Team Structure

### Recommended Team Composition

**Core Team**:
1. **Project Manager / Scrum Master** (1)
   - Overall coordination
   - Stakeholder communication
   - Sprint planning and retrospectives

2. **Senior Backend Developer** (1-2)
   - Odoo module development
   - API integrations (Docebo, PD Platform)
   - Database design and optimization

3. **AI/ML Engineer** (1)
   - RAG implementation (LlamaIndex)
   - LLM integration (Ollama/Llama 3)
   - Embedding and vector store setup

4. **Frontend Developer** (1-2)
   - Vue.js PWA development
   - Odoo OWL components
   - UI/UX implementation

5. **DevOps Engineer** (0.5 - can be shared)
   - Infrastructure setup
   - Docker configuration
   - CI/CD pipeline

6. **QA Engineer** (0.5 - can be shared)
   - Test planning
   - Manual and automated testing
   - UAT coordination

**External Stakeholders**:
- Prudential Business Analyst
- Docebo Administrator
- PD Platform Technical Contact
- End Users (for UAT)

---

## Detailed Phase Breakdown

---

## Phase 1: Foundation & Core Setup (Week 1-2)

### Week 1: Infrastructure & Core Modules

#### Sprint 1 Goal
Setup development environment, database schema, core user management

#### Day 1-2: Environment Setup
**Owner**: DevOps + Senior Backend Developer

**Tasks**:
- [ ] Provision development server (can use local or cloud)
- [ ] Install Odoo 18 CE from source
- [ ] Setup PostgreSQL 15 database
- [ ] Configure Redis for caching
- [ ] Install Celery for background tasks
- [ ] Setup version control (Git repository)
- [ ] Create project directory structure
- [ ] Configure IDE/development environment

**Deliverables**:
- Running Odoo 18 instance
- Database connection verified
- Git repository initialized
- Team development environments setup

**Code**:
```bash
# Initial Odoo setup
git clone https://github.com/odoo/odoo.git --depth 1 --branch 18.0
cd odoo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install psycopg2-binary celery redis

# Create addons directory
mkdir -p /path/to/health-1/addons/pru_core
mkdir -p /path/to/health-1/addons/pru_learning
# ... etc
```

#### Day 3-4: Database Design & Core Models
**Owner**: Senior Backend Developer

**Tasks**:
- [ ] Design complete ERD (Entity Relationship Diagram)
- [ ] Create `pru_core` module structure
- [ ] Implement `pru.profile` model (user profiles)
- [ ] Implement `pru.bank` model (bank partners)
- [ ] Implement `pru.sync.log` model (integration audit trail)
- [ ] Setup security groups and record rules
- [ ] Create basic menu structure
- [ ] Add demo data for testing

**Key Models**:

**pru.profile**:
```python
# addons/pru_core/models/pru_profile.py
from odoo import models, fields, api

class PruProfile(models.Model):
    _name = 'pru.profile'
    _description = 'Prudential User Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Relationship to res.users
    user_id = fields.Many2one('res.users', string='Related User', required=True, ondelete='cascade')
    employee_code = fields.Char('Employee Code', required=True, index=True, tracking=True)

    # Role & Hierarchy
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
    ], string='Role', required=True, tracking=True)

    bank_id = fields.Many2one('pru.bank', string='Bank Partner', required=True, tracking=True)
    manager_id = fields.Many2one('pru.profile', string='Direct Manager', tracking=True)
    team_member_ids = fields.One2many('pru.profile', 'manager_id', string='Team Members')

    # Capability Tracking
    current_capability_segment = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ], string='Capability Level', tracking=True)

    performance_score = fields.Float('Performance Score', digits=(5,2), help='Synced from PD Platform')
    skills_score = fields.Float('Skills Score', digits=(5,2), help='Latest assessment score')
    latest_assessment_date = fields.Date('Latest Assessment Date')

    # Learning metrics
    total_courses_completed = fields.Integer('Courses Completed', compute='_compute_learning_metrics', store=True)
    learning_hours = fields.Float('Total Learning Hours', compute='_compute_learning_metrics', store=True)
    roadmap_completion_rate = fields.Float('Roadmap Completion %', compute='_compute_roadmap_progress')

    # Coaching metrics
    coaching_sessions_count = fields.Integer('Coaching Sessions', compute='_compute_coaching_metrics', store=True)
    last_coaching_date = fields.Date('Last Coaching Date')

    @api.depends('user_id.course_assignment_ids')
    def _compute_learning_metrics(self):
        for profile in self:
            assignments = self.env['pru.course.assignment'].search([
                ('agent_id', '=', profile.id),
                ('state', '=', 'completed')
            ])
            profile.total_courses_completed = len(assignments)
            profile.learning_hours = sum(assignments.mapped('course_id.duration_hours'))

    @api.depends('user_id.coaching_session_ids')
    def _compute_coaching_metrics(self):
        for profile in self:
            sessions = self.env['pru.coaching.session'].search([
                ('agent_id', '=', profile.id),
                ('state', '=', 'completed')
            ])
            profile.coaching_sessions_count = len(sessions)
            if sessions:
                profile.last_coaching_date = max(sessions.mapped('scheduled_date')).date()
```

**pru.bank**:
```python
# addons/pru_core/models/pru_bank.py
class PruBank(models.Model):
    _name = 'pru.bank'
    _description = 'Bank Partner'

    name = fields.Char('Bank Name', required=True)
    code = fields.Char('Bank Code', required=True)
    active = fields.Boolean(default=True)

    # Contacts
    banca_lead_id = fields.Many2one('pru.profile', string='Banca Lead', domain=[('role', '=', 'banca_lead')])
    banca_ho_id = fields.Many2one('pru.profile', string='Banca HO', domain=[('role', '=', 'banca_ho')])

    # Team
    agent_ids = fields.One2many('pru.profile', 'bank_id', string='Agents')
    agent_count = fields.Integer('Agent Count', compute='_compute_agent_count')

    @api.depends('agent_ids')
    def _compute_agent_count(self):
        for bank in self:
            bank.agent_count = len(bank.agent_ids.filtered(lambda a: a.role == 'agent'))
```

**Deliverables**:
- Complete ERD documentation
- Core models implemented with business logic
- Security rules (bank-based isolation)
- Basic forms and list views

#### Day 5: Docebo API Integration Framework
**Owner**: Senior Backend Developer

**Tasks**:
- [ ] Research Docebo API documentation
- [ ] Implement OAuth2 authentication
- [ ] Create `docebo_client.py` service
- [ ] Implement sync logging
- [ ] Test API connection with Docebo sandbox

**Code**:
```python
# addons/pru_learning/services/docebo_client.py
import requests
from datetime import datetime, timedelta
from odoo import fields

class DocebeClient:
    def __init__(self, env):
        self.env = env
        config = env['ir.config_parameter'].sudo()
        self.base_url = config.get_param('pru.docebo_url')
        self.client_id = config.get_param('pru.docebo_client_id')
        self.client_secret = config.get_param('pru.docebo_client_secret')
        self.access_token = None
        self.token_expiry = None

    def authenticate(self):
        """Get OAuth2 access token"""
        if self.access_token and self.token_expiry > datetime.now():
            return self.access_token

        auth_url = f"{self.base_url}/oauth2/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': 'api'
        }
        response = requests.post(auth_url, data=data)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'] - 300)  # 5 min buffer

        return self.access_token

    def _get_headers(self):
        """Get request headers with authentication"""
        token = self.authenticate()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def get_courses(self):
        """Fetch all courses from Docebo"""
        url = f"{self.base_url}/learn/v1/courses"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()['data']['items']

    def get_user_enrollments(self, docebo_user_id):
        """Get enrollments for a specific user"""
        url = f"{self.base_url}/learn/v1/enrollments"
        params = {'user_id': docebo_user_id}
        response = requests.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()['data']['items']

    def enroll_user(self, docebo_user_id, course_id):
        """Enroll user in a course"""
        url = f"{self.base_url}/learn/v1/enrollments"
        data = {
            'user_id': docebo_user_id,
            'course_id': course_id,
            'enrollment_type': 'automatic'
        }
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def log_sync(self, sync_type, status, details):
        """Log sync operation"""
        self.env['pru.sync.log'].create({
            'sync_type': sync_type,
            'system': 'docebo',
            'status': status,
            'details': details,
            'sync_date': fields.Datetime.now(),
        })
```

**Deliverables**:
- Docebo API client working
- Authentication tested
- Basic sync logging functional

---

### Week 2: Learning Module Models & Sync

#### Sprint 2 Goal
Complete learning module models, implement Docebo sync

#### Day 6-7: Learning Module Models
**Owner**: Senior Backend Developer

**Tasks**:
- [ ] Implement `pru.assessment` model
- [ ] Implement `pru.assessment.question` model
- [ ] Implement `pru.assessment.result` model
- [ ] Implement `pru.course` model (synced from Docebo)
- [ ] Implement `pru.course.assignment` model
- [ ] Implement `pru.learning.roadmap` model
- [ ] Implement `pru.capability.segment` model
- [ ] Create views for all models

**Key Model - Assessment**:
```python
# addons/pru_learning/models/pru_assessment.py
class PruAssessment(models.Model):
    _name = 'pru.assessment'
    _description = 'Skills Assessment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Assessment Name', required=True)
    description = fields.Html('Description')
    category = fields.Selection([
        ('sales_skills', 'Sales Skills'),
        ('product_knowledge', 'Product Knowledge'),
        ('customer_service', 'Customer Service'),
        ('compliance', 'Compliance'),
    ], string='Category', required=True)

    question_ids = fields.One2many('pru.assessment.question', 'assessment_id', 'Questions')
    question_count = fields.Integer('Total Questions', compute='_compute_question_count')

    passing_score = fields.Float('Passing Score (%)', default=70.0)
    duration_minutes = fields.Integer('Duration (minutes)', default=60)

    # Auto-enrollment
    auto_enroll = fields.Boolean('Auto-enroll Eligible Agents')
    enrollment_domain = fields.Char('Enrollment Domain')

    # Results
    result_ids = fields.One2many('pru.assessment.result', 'assessment_id', 'Results')

    # Docebo sync
    docebo_course_id = fields.Char('Docebo Course ID')
    sync_to_docebo = fields.Boolean('Sync to Docebo', default=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='draft', tracking=True)

    @api.depends('question_ids')
    def _compute_question_count(self):
        for assessment in self:
            assessment.question_count = len(assessment.question_ids)

    def action_activate(self):
        """Activate assessment and trigger auto-enrollment"""
        self.state = 'active'
        if self.auto_enroll:
            self._auto_enroll_agents()

    def _auto_enroll_agents(self):
        """Auto-enroll agents based on domain"""
        if not self.enrollment_domain:
            return

        domain = safe_eval(self.enrollment_domain)
        agents = self.env['pru.profile'].search(domain)

        for agent in agents:
            # Create assessment result record (pending state)
            self.env['pru.assessment.result'].create({
                'assessment_id': self.id,
                'agent_id': agent.id,
                'state': 'pending',
            })

        # Send notifications
        # ... notification code
```

**Deliverables**:
- All learning models implemented
- Forms, lists, and search views
- Assessment creation wizard

#### Day 8-9: Docebo Data Sync Implementation
**Owner**: Senior Backend Developer

**Tasks**:
- [ ] Implement course sync from Docebo
- [ ] Implement enrollment status sync
- [ ] Implement completion data sync
- [ ] Setup Celery scheduled tasks
- [ ] Create sync status dashboard
- [ ] Error handling and retry logic

**Celery Task**:
```python
# addons/pru_learning/models/docebo_sync.py
from odoo import models, fields, api
from odoo.addons.pru_learning.services.docebo_client import DocebeClient
from celery import shared_task

class DocebeSync(models.Model):
    _name = 'pru.docebo.sync'
    _description = 'Docebo Sync Operations'

    @shared_task(bind=True, max_retries=3)
    def sync_courses(self):
        """Sync courses from Docebo - runs every 24 hours"""
        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        client = DocebeClient(env)

        try:
            docebo_courses = client.get_courses()

            for course_data in docebo_courses:
                # Find or create course
                course = env['pru.course'].search([('docebo_id', '=', course_data['id'])], limit=1)

                vals = {
                    'name': course_data['name'],
                    'description': course_data['description'],
                    'docebo_id': course_data['id'],
                    'duration_hours': course_data.get('duration', 0) / 3600,  # seconds to hours
                    'category': self._map_category(course_data.get('category')),
                }

                if course:
                    course.write(vals)
                else:
                    env['pru.course'].create(vals)

            client.log_sync('courses', 'success', f'Synced {len(docebo_courses)} courses')

        except Exception as e:
            client.log_sync('courses', 'error', str(e))
            raise

    @shared_task(bind=True, max_retries=3)
    def sync_enrollments(self):
        """Sync enrollment status - runs every 15 minutes"""
        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        client = DocebeClient(env)

        # Get all agents with Docebo IDs
        agents = env['pru.profile'].search([('docebo_user_id', '!=', False)])

        for agent in agents:
            try:
                enrollments = client.get_user_enrollments(agent.docebo_user_id)

                for enrollment in enrollments:
                    assignment = env['pru.course.assignment'].search([
                        ('agent_id', '=', agent.id),
                        ('course_id.docebo_id', '=', enrollment['course_id']),
                    ], limit=1)

                    vals = {
                        'completion_status': enrollment['completion_status'],
                        'completion_date': enrollment.get('completion_date'),
                        'score': enrollment.get('score', 0.0),
                    }

                    if enrollment['completion_status'] == 'completed':
                        vals['state'] = 'completed'

                    if assignment:
                        assignment.write(vals)

            except Exception as e:
                client.log_sync('enrollments', 'error', f'Agent {agent.employee_code}: {str(e)}')

        client.log_sync('enrollments', 'success', f'Synced enrollments for {len(agents)} agents')
```

**Celery Beat Schedule**:
```python
# addons/pru_learning/__manifest__.py
{
    'name': 'PruLearn360 - Learning Management',
    # ...
    'external_dependencies': {
        'python': ['celery', 'redis'],
    },
    'data': [
        # ...
        'data/celery_schedule.xml',
    ],
}

# addons/pru_learning/data/celery_schedule.xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">

    <record id="celery_task_sync_courses" model="ir.cron">
        <field name="name">Docebo: Sync Courses</field>
        <field name="model_id" ref="model_pru_docebo_sync"/>
        <field name="state">code</field>
        <field name="code">model.sync_courses()</field>
        <field name="interval_number">24</field>
        <field name="interval_type">hours</field>
        <field name="numbercall">-1</field>
        <field name="active" eval="True"/>
    </record>

    <record id="celery_task_sync_enrollments" model="ir.cron">
        <field name="name">Docebo: Sync Enrollments</field>
        <field name="model_id" ref="model_pru_docebo_sync"/>
        <field name="state">code</field>
        <field name="code">model.sync_enrollments()</field>
        <field name="interval_number">15</field>
        <field name="interval_type">minutes</field>
        <field name="numbercall">-1</field>
        <field name="active" eval="True"/>
    </record>

</odoo>
```

**Deliverables**:
- Docebo sync working end-to-end
- Celery tasks scheduled
- Sync monitoring dashboard

#### Day 10: Dashboard & Views
**Owner**: Frontend Developer + Senior Backend Developer

**Tasks**:
- [ ] Create admin dashboard (Odoo views)
- [ ] Create agent dashboard (personal view)
- [ ] Role-based dashboard routing
- [ ] Dashboard KPI widgets
- [ ] Navigation menu structure

**Deliverables**:
- Role-based dashboards functional
- KPI widgets showing real data

---

## Phase 2: Capability Management & PD Integration (Week 3-4)

### Week 3: Assessment Engine & Capability Segmentation

#### Sprint 3 Goal
Skills assessment functional, capability segmentation working

#### Day 11-12: Assessment Wizard & Taking Logic
**Owner**: Frontend Developer + Backend Developer

**Tasks**:
- [ ] Assessment wizard UI (OWL component or standard wizard)
- [ ] Question display logic
- [ ] Answer submission
- [ ] Auto-scoring algorithm
- [ ] Result calculation
- [ ] Result display page
- [ ] Certificate generation (optional)

**Assessment Wizard**:
```python
# addons/pru_learning/wizards/assessment_wizard.py
class AssessmentWizard(models.TransientModel):
    _name = 'pru.assessment.wizard'
    _description = 'Take Assessment Wizard'

    assessment_id = fields.Many2one('pru.assessment', 'Assessment', required=True)
    agent_id = fields.Many2one('pru.profile', 'Agent', default=lambda self: self.env.user.pru_profile_id)

    # Wizard flow
    current_question_index = fields.Integer(default=0)
    current_question_id = fields.Many2one('pru.assessment.question', compute='_compute_current_question')

    # Answers storage (JSON)
    answers_json = fields.Text('Answers (JSON)', default='{}')

    start_time = fields.Datetime('Start Time', default=fields.Datetime.now)

    @api.depends('current_question_index', 'assessment_id')
    def _compute_current_question(self):
        for wizard in self:
            questions = wizard.assessment_id.question_ids.sorted('sequence')
            if 0 <= wizard.current_question_index < len(questions):
                wizard.current_question_id = questions[wizard.current_question_index]
            else:
                wizard.current_question_id = False

    def action_next_question(self):
        """Move to next question"""
        self.current_question_index += 1
        return self._reload_wizard()

    def action_previous_question(self):
        """Go back to previous question"""
        self.current_question_index -= 1
        return self._reload_wizard()

    def action_submit_assessment(self):
        """Submit assessment and calculate score"""
        answers = json.loads(self.answers_json or '{}')

        # Calculate score
        total_questions = len(self.assessment_id.question_ids)
        correct_answers = 0

        for question in self.assessment_id.question_ids:
            user_answer = answers.get(str(question.id))
            if user_answer == question.correct_answer:
                correct_answers += 1

        score = (correct_answers / total_questions * 100) if total_questions > 0 else 0.0

        # Create result record
        result = self.env['pru.assessment.result'].create({
            'assessment_id': self.assessment_id.id,
            'agent_id': self.agent_id.id,
            'score': score,
            'answers_json': self.answers_json,
            'start_time': self.start_time,
            'end_time': fields.Datetime.now(),
            'state': 'passed' if score >= self.assessment_id.passing_score else 'failed',
        })

        # Update agent capability
        self.agent_id.write({
            'skills_score': score,
            'latest_assessment_date': fields.Date.today(),
        })

        # Trigger capability recalculation
        self.agent_id._compute_capability_segment()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Assessment Result',
            'res_model': 'pru.assessment.result',
            'res_id': result.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reload_wizard(self):
        """Reload wizard view"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
```

**Deliverables**:
- Assessment wizard functional
- Agents can take assessments
- Auto-scoring working
- Results saved

#### Day 13-14: Capability Segmentation Algorithm
**Owner**: Backend Developer + AI Engineer

**Tasks**:
- [ ] Design capability matrix (Performance × Skills)
- [ ] Implement segmentation rules
- [ ] Auto-classification on data update
- [ ] Capability history tracking
- [ ] Capability matrix heatmap view

**Capability Segmentation**:
```python
# addons/pru_learning/models/pru_capability_segment.py
class PruCapabilitySegment(models.Model):
    _name = 'pru.capability.segment'
    _description = 'Capability Segmentation Rules'

    name = fields.Char('Rule Name', required=True)
    capability_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ], required=True)

    # Segmentation criteria
    min_performance_score = fields.Float('Min Performance Score')
    max_performance_score = fields.Float('Max Performance Score')
    min_skills_score = fields.Float('Min Skills Score')
    max_skills_score = fields.Float('Max Skills Score')

    # Actions
    roadmap_id = fields.Many2one('pru.learning.roadmap', 'Assigned Roadmap')
    auto_assign_roadmap = fields.Boolean('Auto-assign Roadmap', default=True)

    sequence = fields.Integer('Priority', default=10, help='Lower = higher priority')

    @api.model
    def classify_agent(self, agent):
        """Classify agent based on performance and skills scores"""
        rules = self.search([], order='sequence')

        for rule in rules:
            if (rule.min_performance_score <= agent.performance_score <= rule.max_performance_score and
                rule.min_skills_score <= agent.skills_score <= rule.max_skills_score):

                # Update agent capability
                agent.write({'current_capability_segment': rule.capability_level})

                # Auto-assign roadmap
                if rule.auto_assign_roadmap and rule.roadmap_id:
                    self._assign_roadmap(agent, rule.roadmap_id)

                # Log history
                self.env['pru.capability.history'].create({
                    'agent_id': agent.id,
                    'capability_level': rule.capability_level,
                    'performance_score': agent.performance_score,
                    'skills_score': agent.skills_score,
                    'date': fields.Date.today(),
                })

                return rule.capability_level

        return False

    def _assign_roadmap(self, agent, roadmap):
        """Assign learning roadmap to agent"""
        # Create course assignments
        for course in roadmap.course_ids:
            existing = self.env['pru.course.assignment'].search([
                ('agent_id', '=', agent.id),
                ('course_id', '=', course.id),
                ('state', '!=', 'completed'),
            ], limit=1)

            if not existing:
                self.env['pru.course.assignment'].create({
                    'agent_id': agent.id,
                    'course_id': course.id,
                    'roadmap_id': roadmap.id,
                    'state': 'assigned',
                })

        # Enroll in Docebo
        # ... enrollment code
```

**Deliverables**:
- Capability segmentation rules configurable
- Auto-classification working
- Roadmap auto-assignment functional

#### Day 15: Learning Roadmap Automation
**Owner**: Backend Developer

**Tasks**:
- [ ] Roadmap templates setup
- [ ] Auto-enrollment to Docebo integration
- [ ] Progress tracking logic
- [ ] Completion notifications
- [ ] Roadmap timeline view

**Deliverables**:
- End-to-end roadmap automation
- Agents enrolled automatically in Docebo

---

### Week 4: PD Platform Integration & Microlearning

#### Sprint 4 Goal
PD Platform integration, real-time capability updates, microlearning

#### Day 16-17: PD Platform Integration
**Owner**: Senior Backend Developer

**Tasks**:
- [ ] Research PD Platform API documentation
- [ ] Implement API authentication
- [ ] Create `pd_client.py` service
- [ ] Performance data sync (every 5 minutes)
- [ ] Trigger capability recalculation on performance update
- [ ] Performance trend visualization

**PD Platform Client**:
```python
# addons/pru_coaching/services/pd_client.py
import requests
from datetime import datetime

class PDPlatformClient:
    def __init__(self, env):
        self.env = env
        config = env['ir.config_parameter'].sudo()
        self.base_url = config.get_param('pru.pd_platform_url')
        self.api_key = config.get_param('pru.pd_platform_api_key')

    def _get_headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_agent_performance(self, pd_agent_id):
        """Get performance data for agent"""
        url = f"{self.base_url}/api/v1/agents/{pd_agent_id}/performance"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_coaching_sessions(self, pd_agent_id):
        """Get coaching session history"""
        url = f"{self.base_url}/api/v1/coaching-sessions"
        params = {'agent_id': pd_agent_id}
        response = requests.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def sync_performance_data(self):
        """Sync performance data for all agents"""
        agents = self.env['pru.profile'].search([('pd_agent_id', '!=', False)])

        for agent in agents:
            try:
                performance = self.get_agent_performance(agent.pd_agent_id)

                # Update performance score
                old_score = agent.performance_score
                new_score = performance.get('overall_score', 0.0)

                agent.write({'performance_score': new_score})

                # Trigger capability recalculation if score changed significantly
                if abs(new_score - old_score) >= 5.0:  # 5 point threshold
                    self.env['pru.capability.segment'].classify_agent(agent)

                    # Send notification if capability level changed
                    # ...

            except Exception as e:
                self.env['pru.sync.log'].create({
                    'sync_type': 'performance',
                    'system': 'pd_platform',
                    'status': 'error',
                    'details': f'Agent {agent.employee_code}: {str(e)}',
                })
```

**Celery Task** (5-minute interval):
```python
@shared_task(bind=True)
def sync_pd_performance(self):
    """Sync performance data from PD Platform - runs every 5 minutes"""
    env = api.Environment(self.env.cr, SUPERUSER_ID, {})
    client = PDPlatformClient(env)
    client.sync_performance_data()
```

**Deliverables**:
- PD Platform integration working
- Real-time performance sync (5 min)
- Capability auto-recalculation

#### Day 18-19: Microlearning Suggestion Engine
**Owner**: Backend Developer + AI Engineer

**Tasks**:
- [ ] Skill gap analysis algorithm
- [ ] Course recommendation logic
- [ ] Microlearning assignment rules
- [ ] Auto-assign to Docebo
- [ ] Microlearning progress tracking

**Deliverables**:
- Microlearning recommendations functional
- Auto-assignment to Docebo working

#### Day 20: Re-assessment Workflow
**Owner**: Backend Developer

**Tasks**:
- [ ] Re-assessment eligibility calculation
- [ ] Attempt tracking (max attempts per month)
- [ ] Notification system for re-assessment
- [ ] Re-assessment history
- [ ] Performance comparison (before/after)

**Deliverables**:
- Re-assessment workflow complete
- Notifications working

---

## Phase 3: Coaching & Ticketing (Week 5)

### Week 5: Sales Companion Features

#### Sprint 5 Goal
Coaching scheduler, action plans, behavior assessment, ticketing

#### Day 21-22: Coaching Session Management
**Owner**: Backend + Frontend Developer

**Tasks**:
- [ ] Implement `pru.coaching.session` model
- [ ] Calendar view (drag-drop scheduling)
- [ ] Notification system (email + in-app)
- [ ] Session notes and scoring
- [ ] Coach dashboard

**Deliverables**:
- Coaching sessions can be scheduled
- Calendar view functional
- Notifications sent

#### Day 23: Action Plan & Behavior Assessment
**Owner**: Backend Developer

**Tasks**:
- [ ] Implement `pru.action.plan` model
- [ ] Action plan form builder
- [ ] Completion tracking
- [ ] Implement `pru.behavior.assessment` model
- [ ] Banca+ step configuration
- [ ] Manager assessment workflow

**Deliverables**:
- Action plans working
- Behavior assessments functional

#### Day 24-25: Ticket Management System
**Owner**: Backend + Frontend Developer

**Tasks**:
- [ ] Implement `pru.ticket` model
- [ ] Ticket creation form
- [ ] Approval workflow
- [ ] Auto-create training sessions on approval
- [ ] Kanban board view
- [ ] Email notifications

**Deliverables**:
- Training request ticketing complete
- Approval workflow functional
- Training session auto-creation working

---

## Phase 4: Analytics & AI (Week 6)

### Week 6: Dashboards & AI Chatbot

#### Sprint 6 Goal
Metabase dashboards embedded, AI chatbot functional

#### Day 26-27: Metabase Setup & Dashboard Creation
**Owner**: Backend Developer + Data Analyst

**Tasks**:
- [ ] Deploy Metabase (Docker)
- [ ] Connect to Odoo PostgreSQL database
- [ ] Create 4 dashboards:
  - Executive Dashboard (PVA Admin)
  - Bank Leader Dashboard (Banca Lead)
  - Agent Personal Dashboard
  - Trainer Dashboard
- [ ] Configure JWT embedding
- [ ] Implement embed controller in Odoo
- [ ] Test embedded dashboards in Odoo views

**Metabase Embed Controller**:
```python
# addons/pru_analytics/controllers/metabase_embed.py
from odoo import http
from odoo.http import request
import jwt
import time

class MetabaseEmbedController(http.Controller):

    @http.route('/pru/dashboard/<int:dashboard_id>', auth='user', website=True)
    def embed_dashboard(self, dashboard_id, **kw):
        """Render Metabase dashboard with JWT token"""
        user = request.env.user
        profile = user.pru_profile_id

        # Generate JWT token
        metabase_secret = request.env['ir.config_parameter'].sudo().get_param('pru.metabase_secret_key')

        payload = {
            "resource": {"dashboard": dashboard_id},
            "params": {
                "bank_id": profile.bank_id.id,
                "user_role": profile.role,
                "user_id": profile.id,
            },
            "exp": int(time.time()) + (60 * 60),  # 1 hour expiry
        }

        token = jwt.encode(payload, metabase_secret, algorithm="HS256")

        metabase_url = request.env['ir.config_parameter'].sudo().get_param('pru.metabase_url')
        embed_url = f"{metabase_url}/embed/dashboard/{token}#bordered=false&titled=false"

        return request.render('pru_analytics.metabase_dashboard_template', {
            'embed_url': embed_url,
            'dashboard_name': kw.get('name', 'Dashboard'),
        })
```

**Deliverables**:
- 4 dashboards created in Metabase
- JWT embedding working
- Dashboards accessible in Odoo

#### Day 28-29: AI Chatbot - Ollama & LlamaIndex Setup
**Owner**: AI Engineer

**Tasks**:
- [ ] Deploy Ollama (Docker or local)
- [ ] Download Llama 3.2 model (8B)
- [ ] Setup ChromaDB
- [ ] Implement knowledge ingestion pipeline
- [ ] Implement RAG query engine (LlamaIndex)
- [ ] Test Q&A accuracy

**Knowledge Ingestion**:
```python
# addons/pru_ai/services/knowledge_ingestion.py
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

def ingest_sales_documents():
    """Ingest sales knowledge documents"""
    # Initialize Chroma client
    chroma_client = chromadb.PersistentClient(path="/opt/odoo/chromadb")

    # Initialize embedding model (multilingual)
    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # Load documents
    documents = SimpleDirectoryReader("/opt/odoo/knowledge_base").load_data()

    # Create collection
    collection = chroma_client.get_or_create_collection("pru_sales_knowledge")
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Create index
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
    )

    return index
```

**Deliverables**:
- Ollama running with Llama 3
- Knowledge base ingested
- RAG query working

#### Day 30: AI Chatbot - Frontend Widget
**Owner**: Frontend Developer

**Tasks**:
- [ ] Implement OWL chatbot widget
- [ ] Floating chat button
- [ ] Message history display
- [ ] Source citations
- [ ] Feedback buttons
- [ ] Mobile responsive

**Deliverables**:
- Chatbot widget functional
- Users can ask questions and get answers

---

## Phase 5: Mobile PWA & UI Polish (Week 7)

### Week 7: Mobile Application & UI Refinement

#### Sprint 7 Goal
Mobile PWA installable, offline-capable, polished UI

#### Day 31-32: Vue.js PWA Setup & Core Screens
**Owner**: Frontend Developer

**Tasks**:
- [ ] Vue.js 3 + Quasar project setup
- [ ] PWA configuration (manifest.json, service worker)
- [ ] Implement 7 core screens:
  1. Login/Auth
  2. Dashboard
  3. Learning Path
  4. Coaching Schedule
  5. Action Plans
  6. AI Chatbot
  7. Profile
- [ ] Bottom navigation
- [ ] API integration with Odoo

**Deliverables**:
- PWA installable on mobile
- Core screens functional

#### Day 33: Offline Functionality (PouchDB)
**Owner**: Frontend Developer

**Tasks**:
- [ ] Setup PouchDB
- [ ] Offline form storage
- [ ] Background sync on reconnect
- [ ] Conflict resolution
- [ ] Offline indicator UI

**Deliverables**:
- Forms work offline
- Data syncs when online

#### Day 34-35: UI/UX Polish (Tailwind CSS)
**Owner**: Frontend Developer + Designer

**Tasks**:
- [ ] Implement Tailwind CSS design system
- [ ] Custom Prudential color palette
- [ ] Component library (cards, buttons, badges)
- [ ] Loading states and skeletons
- [ ] Empty states
- [ ] Toast notifications
- [ ] Modal dialogs
- [ ] Responsive testing (mobile, tablet, desktop)

**Deliverables**:
- Consistent UI across all screens
- Professional design aesthetic

---

## Phase 6: Testing, Documentation & Deployment (Week 8)

### Week 8: Quality Assurance & Launch

#### Sprint 8 Goal
Production-ready system with documentation

#### Day 36-37: Testing
**Owner**: QA Engineer + All Developers

**Tasks**:
- [ ] Unit tests (Python models)
- [ ] API integration tests
- [ ] Frontend component tests (Vitest)
- [ ] E2E tests (Playwright)
- [ ] Performance testing (Locust)
- [ ] Security audit (OWASP)
- [ ] Cross-browser testing
- [ ] Mobile device testing
- [ ] Bug fixes

**Test Coverage Target**: 70%+

**Deliverables**:
- Test suite passing
- Critical bugs fixed

#### Day 38-39: Documentation
**Owner**: Technical Writer + Developers

**Tasks**:
- [ ] Technical documentation:
  - Architecture diagrams
  - Data model ERD
  - API documentation
  - Deployment guide
- [ ] User documentation:
  - Admin guide
  - User manuals (per role)
  - Video tutorials (10+ videos)
  - FAQ document
- [ ] Developer documentation:
  - Code comments
  - Development setup guide
  - Contributing guidelines

**Deliverables**:
- Complete documentation package

#### Day 40-42: Production Deployment
**Owner**: DevOps Engineer + Senior Developer

**Tasks**:
- [ ] Production server setup (Hetzner CX41)
- [ ] Docker Compose deployment
- [ ] Nginx configuration
- [ ] SSL certificate (Let's Encrypt)
- [ ] PostgreSQL optimization
- [ ] Redis configuration
- [ ] Ollama deployment
- [ ] Metabase deployment
- [ ] Backup automation
- [ ] Monitoring setup (optional Grafana)
- [ ] Data migration (existing users)
- [ ] Smoke testing in production
- [ ] Phased rollout (pilot group)
- [ ] Training sessions for admins
- [ ] Go-live announcement

**Deliverables**:
- Production system live
- Monitoring active
- Users onboarded

---

## Risk Management

### Identified Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|-----------|--------|---------------------|
| Docebo API changes/downtime | Medium | High | Implement robust error handling, fallback mechanisms, sync queue |
| PD Platform API unavailable | Medium | High | Graceful degradation, cached data, manual entry option |
| LLM hallucinations | High | Medium | Confidence scoring, source citations, user feedback loop |
| Performance issues (LLM) | Medium | Medium | GPU acceleration, model optimization, response caching |
| Scope creep | Medium | High | Strict change control, prioritize MVP features |
| Resource availability | Low | High | Cross-training team members, documentation |
| Security vulnerabilities | Low | Critical | Security audit, penetration testing, regular updates |
| User adoption resistance | Medium | High | Training, change management, stakeholder engagement |
| Data migration issues | Medium | Medium | Thorough testing, rollback plan, parallel run |

---

## Success Criteria

### Phase Completion Criteria

**Phase 1 Complete**:
- ✅ User management functional
- ✅ Docebo sync working (courses, enrollments)
- ✅ Admin dashboard showing synced data

**Phase 2 Complete**:
- ✅ Skills assessment working end-to-end
- ✅ Capability segmentation auto-classifying agents
- ✅ Learning roadmap auto-assignment functional
- ✅ PD Platform sync working

**Phase 3 Complete**:
- ✅ Coaching sessions schedulable
- ✅ Action plans and behavior assessments functional
- ✅ Ticket system working with approval workflow

**Phase 4 Complete**:
- ✅ Metabase dashboards embedded in Odoo
- ✅ AI chatbot answering sales questions accurately (80%+ satisfaction)

**Phase 5 Complete**:
- ✅ Mobile PWA installable
- ✅ Offline forms working
- ✅ UI polished and responsive

**Phase 6 Complete**:
- ✅ Test coverage 70%+
- ✅ Documentation complete
- ✅ Production deployment successful
- ✅ 90%+ user login rate in first month

---

## Post-Launch Support Plan

### Month 1: Stabilization
- Daily monitoring
- Bug fix priority
- User feedback collection
- Performance tuning

### Month 2-3: Optimization
- Feature enhancements based on feedback
- Performance optimization
- Additional training sessions
- Success metrics review

### Month 4-6: Iteration
- Quarterly roadmap planning
- Feature releases (2-week sprints)
- Continuous improvement

---

## Appendix

### Development Environment Setup Guide

**Prerequisites**:
- Python 3.10+
- PostgreSQL 15
- Redis 7
- Node.js 20 LTS
- Git

**Setup Steps**:
```bash
# 1. Clone Odoo 18
git clone https://github.com/odoo/odoo.git --depth 1 --branch 18.0
cd odoo

# 2. Setup Python virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install psycopg2-binary celery redis llama-index chromadb sentence-transformers

# 4. Clone project addons
cd ../
git clone <project-repo> health-1
cd health-1/addons

# 5. Configure Odoo
cat > ../config/odoo.conf << EOF
[options]
addons_path = /path/to/odoo/addons,/path/to/health-1/addons
db_host = localhost
db_port = 5432
db_user = odoo
db_password = odoo
http_port = 8069
workers = 4
EOF

# 6. Create database
createdb prulearn360

# 7. Start Odoo
../odoo/odoo-bin -c config/odoo.conf -d prulearn360 -i pru_core,pru_learning,pru_coaching,pru_analytics,pru_tickets,pru_ai,pru_mobile

# 8. Start Redis
redis-server

# 9. Start Celery
celery -A odoo worker -l info

# 10. Setup Ollama
curl https://ollama.ai/install.sh | sh
ollama pull llama3.2:8b

# 11. Setup Metabase
docker run -d -p 3000:3000 --name metabase metabase/metabase
```

---

**Document Version**: 1.0
**Last Updated**: October 27, 2025
**Status**: Ready for Execution
