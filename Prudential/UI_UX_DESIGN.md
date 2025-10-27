# PruLearn360 - UI/UX Design Specification

## Design Philosophy

**"Enterprise Professional meets Consumer-Grade Polish"**

PruLearn360's interface combines the professionalism expected in enterprise software with the intuitive, delightful experience of consumer applications. Our design draws inspiration from industry leaders while maintaining Prudential's brand identity.

---

## Design Principles

### 1. **Mobile-First Responsive**
- Design for mobile screens first, scale up to desktop
- Touch-friendly controls (minimum 44×44px tap targets)
- Thumb-friendly navigation zones
- Progressive enhancement for larger screens

### 2. **Progressive Disclosure**
- Show only essential information initially
- Reveal complexity gradually as needed
- Minimize cognitive load
- Clear visual hierarchy

### 3. **Consistency & Familiarity**
- Consistent patterns across all modules
- Familiar UI paradigms (icons, gestures)
- Predictable navigation
- Standardized component library

### 4. **Performance & Speed**
- Optimistic UI updates
- Skeleton screens while loading
- Perceived performance optimization
- Instant feedback on interactions

### 5. **Accessibility First**
- WCAG 2.1 AA compliance
- Keyboard navigation support
- Screen reader compatibility
- High contrast mode support
- Color-blind friendly palettes

---

## Design Inspirations & References

### LinkedIn Learning
**Adopted Elements**:
- Clean course card design with progress indicators
- Learning path visualization (timeline view)
- Certificate badges
- "Continue learning" quick access
- Skill tags and categories

### Monday.com
**Adopted Elements**:
- Colorful status indicators (visual status system)
- Kanban board interaction patterns
- Quick filters and grouping
- Activity timeline
- @mentions and notifications

### Notion
**Adopted Elements**:
- Minimalist information hierarchy
- Nested navigation (sidebar + breadcrumbs)
- Inline editing paradigm
- Database views (table, board, calendar)
- Clean typography

### Tableau
**Adopted Elements**:
- Professional dashboard layouts
- KPI card designs
- Data visualization best practices
- Filter panels
- Drill-down interactions

### Slack
**Adopted Elements**:
- Notification center design
- Conversational UI (chatbot)
- Channel/thread organization
- Emoji reactions
- Mobile bottom navigation

### Asana
**Adopted Elements**:
- Task/action plan cards
- Timeline view (Gantt-style)
- Team collaboration features
- Progress tracking
- Due date visualization

---

## Brand Identity

### Prudential Brand Colors

**Primary Colors**:
```css
--pru-red: #ED1B2E;              /* Prudential Red - Primary CTA */
--pru-red-dark: #C41628;         /* Hover states */
--pru-red-light: #FF4D5E;        /* Backgrounds, accents */
--pru-red-lighter: #FFE5E8;      /* Subtle backgrounds */
```

**Secondary Colors**:
```css
--pru-blue: #003DA5;             /* Professional Blue - Secondary */
--pru-blue-dark: #002D7A;
--pru-blue-light: #3366CC;
--pru-blue-lighter: #E6EEFF;
```

**Accent Colors** (for capability levels, status):
```css
--accent-success: #00C9A7;       /* Success, Expert level */
--accent-warning: #FFB020;       /* Warning, Intermediate level */
--accent-danger: #E63946;        /* Error, Beginner level */
--accent-info: #3B82F6;          /* Info, Advanced level */
```

**Neutral Grays** (following Tailwind Gray palette):
```css
--gray-50: #F9FAFB;              /* Backgrounds */
--gray-100: #F3F4F6;             /* Subtle backgrounds */
--gray-200: #E5E7EB;             /* Borders */
--gray-300: #D1D5DB;             /* Borders (stronger) */
--gray-400: #9CA3AF;             /* Disabled text */
--gray-500: #6B7280;             /* Secondary text */
--gray-600: #4B5563;             /* Body text */
--gray-700: #374151;             /* Headings */
--gray-800: #1F2937;             /* Strong headings */
--gray-900: #111827;             /* Primary text */
```

### Typography System

**Font Family**:
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
             Roboto, 'Helvetica Neue', Arial, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
```

**Font Sizes** (following Tailwind scale):
```css
--text-xs: 0.75rem;      /* 12px - Captions, labels */
--text-sm: 0.875rem;     /* 14px - Secondary text, buttons */
--text-base: 1rem;       /* 16px - Body text */
--text-lg: 1.125rem;     /* 18px - Large body, card titles */
--text-xl: 1.25rem;      /* 20px - Section headings */
--text-2xl: 1.5rem;      /* 24px - Page headings */
--text-3xl: 1.875rem;    /* 30px - Hero headings */
--text-4xl: 2.25rem;     /* 36px - Dashboard numbers */
```

**Font Weights**:
```css
--font-normal: 400;
--font-medium: 500;      /* Card titles, labels */
--font-semibold: 600;    /* Headings, emphasis */
--font-bold: 700;        /* Strong emphasis */
```

**Line Heights**:
```css
--leading-tight: 1.25;   /* Headings */
--leading-normal: 1.5;   /* Body text */
--leading-relaxed: 1.75; /* Comfortable reading */
```

### Spacing System

**Base Unit**: 4px (0.25rem)

```css
--space-0: 0;
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-5: 1.25rem;   /* 20px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
--space-10: 2.5rem;   /* 40px */
--space-12: 3rem;     /* 48px */
--space-16: 4rem;     /* 64px */
--space-20: 5rem;     /* 80px */
```

### Border Radius

```css
--radius-none: 0;
--radius-sm: 0.25rem;    /* 4px - Small buttons */
--radius-md: 0.375rem;   /* 6px - Inputs, cards */
--radius-lg: 0.5rem;     /* 8px - Larger cards */
--radius-xl: 0.75rem;    /* 12px - Modals */
--radius-2xl: 1rem;      /* 16px - Hero cards */
--radius-full: 9999px;   /* Pills, avatars */
```

### Shadows

```css
--shadow-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.1),
             0 1px 2px -1px rgba(0, 0, 0, 0.1);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
             0 2px 4px -2px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1),
             0 4px 6px -4px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1),
             0 8px 10px -6px rgba(0, 0, 0, 0.1);
--shadow-2xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
```

---

## Component Library

### 1. Cards

#### Metric Card
**Use**: Dashboard KPI display

```html
<div class="pru-card pru-card-metric">
  <div class="card-header">
    <div class="metric-label">
      <span class="icon">📊</span>
      <span class="text">Capability Score</span>
    </div>
    <div class="metric-trend positive">
      <span class="icon">↑</span>
      <span class="value">+12%</span>
    </div>
  </div>

  <div class="card-body">
    <div class="metric-value">8.7</div>
    <div class="metric-subtitle">out of 10.0</div>
  </div>

  <div class="card-footer">
    <div class="progress-bar">
      <div class="progress-fill" style="width: 87%"></div>
    </div>
    <div class="progress-label">
      <span>Beginner</span>
      <span>Expert</span>
    </div>
  </div>
</div>
```

**CSS**:
```css
.pru-card {
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s, transform 0.2s;
}

.pru-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.pru-card-metric {
  padding: var(--space-6);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.metric-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--gray-600);
}

.metric-trend {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
}

.metric-trend.positive {
  background: var(--accent-success);
  color: white;
}

.metric-trend.negative {
  background: var(--accent-danger);
  color: white;
}

.metric-value {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  color: var(--pru-red);
  line-height: var(--leading-tight);
}

.metric-subtitle {
  font-size: var(--text-sm);
  color: var(--gray-500);
  margin-top: var(--space-1);
}

.progress-bar {
  height: 8px;
  background: var(--gray-200);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-top: var(--space-4);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--pru-red), var(--pru-red-light));
  border-radius: var(--radius-full);
  transition: width 0.6s ease;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--gray-500);
  margin-top: var(--space-2);
}
```

#### Course Card
**Use**: Learning path display

```html
<div class="pru-card pru-card-course">
  <div class="course-image">
    <img src="/static/img/course-thumbnail.jpg" alt="Course">
    <div class="course-duration">
      <span class="icon">⏱</span>
      <span>2.5 hrs</span>
    </div>
  </div>

  <div class="card-body">
    <div class="course-category">Sales Skills</div>
    <h3 class="course-title">Advanced Sales Techniques</h3>
    <p class="course-description">
      Master the art of consultative selling and objection handling.
    </p>

    <div class="course-meta">
      <span class="meta-item">
        <span class="icon">👤</span>
        <span>1,234 learners</span>
      </span>
      <span class="meta-item">
        <span class="icon">⭐</span>
        <span>4.8</span>
      </span>
    </div>

    <div class="course-progress">
      <div class="progress-bar">
        <div class="progress-fill" style="width: 60%"></div>
      </div>
      <span class="progress-text">60% complete</span>
    </div>
  </div>

  <div class="card-footer">
    <button class="btn btn-primary btn-block">Continue Learning</button>
  </div>
</div>
```

**CSS**:
```css
.pru-card-course {
  max-width: 320px;
  overflow: hidden;
}

.course-image {
  position: relative;
  aspect-ratio: 16/9;
  background: var(--gray-200);
  overflow: hidden;
}

.course-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.course-duration {
  position: absolute;
  bottom: var(--space-2);
  right: var(--space-2);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.course-category {
  display: inline-block;
  background: var(--pru-red-lighter);
  color: var(--pru-red-dark);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-2);
}

.course-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--gray-900);
  margin-bottom: var(--space-2);
  line-height: var(--leading-tight);
}

.course-description {
  font-size: var(--text-sm);
  color: var(--gray-600);
  line-height: var(--leading-normal);
  margin-bottom: var(--space-4);
}

.course-meta {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--gray-600);
}

.course-progress {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.course-progress .progress-bar {
  flex: 1;
  height: 6px;
}

.progress-text {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--gray-600);
  white-space: nowrap;
}
```

### 2. Buttons

```html
<!-- Primary Button -->
<button class="btn btn-primary">
  <span class="btn-icon">✓</span>
  <span>Save Changes</span>
</button>

<!-- Secondary Button -->
<button class="btn btn-secondary">Cancel</button>

<!-- Outline Button -->
<button class="btn btn-outline">View Details</button>

<!-- Icon Button -->
<button class="btn btn-icon">
  <span>🔔</span>
</button>

<!-- Loading State -->
<button class="btn btn-primary" disabled>
  <span class="spinner"></span>
  <span>Processing...</span>
</button>
```

**CSS**:
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  text-decoration: none;
}

.btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn:active {
  transform: translateY(0);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn-primary {
  background: var(--pru-red);
  color: white;
  border-color: var(--pru-red);
}

.btn-primary:hover {
  background: var(--pru-red-dark);
  border-color: var(--pru-red-dark);
}

.btn-secondary {
  background: var(--gray-200);
  color: var(--gray-700);
  border-color: var(--gray-200);
}

.btn-secondary:hover {
  background: var(--gray-300);
  border-color: var(--gray-300);
}

.btn-outline {
  background: transparent;
  color: var(--pru-red);
  border-color: var(--pru-red);
}

.btn-outline:hover {
  background: var(--pru-red-lighter);
}

.btn-icon {
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: var(--radius-full);
}

.btn-block {
  width: 100%;
}

.btn-sm {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
}

.btn-lg {
  padding: var(--space-4) var(--space-6);
  font-size: var(--text-base);
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### 3. Forms

```html
<div class="form-group">
  <label class="form-label" for="email">
    Email Address
    <span class="required">*</span>
  </label>
  <input
    type="email"
    id="email"
    class="form-control"
    placeholder="agent@prudential.com"
    required
  />
  <span class="form-help">We'll never share your email.</span>
</div>

<div class="form-group">
  <label class="form-label" for="role">Role</label>
  <select id="role" class="form-control">
    <option value="">Select role...</option>
    <option value="agent">Agent</option>
    <option value="bdm">BDM</option>
  </select>
</div>

<div class="form-group">
  <label class="form-label">Preferences</label>
  <div class="form-checkbox">
    <input type="checkbox" id="notifications" />
    <label for="notifications">Enable notifications</label>
  </div>
  <div class="form-checkbox">
    <input type="checkbox" id="newsletter" />
    <label for="newsletter">Subscribe to newsletter</label>
  </div>
</div>

<!-- Error State -->
<div class="form-group has-error">
  <label class="form-label" for="password">Password</label>
  <input type="password" id="password" class="form-control" />
  <span class="form-error">Password must be at least 8 characters</span>
</div>
```

**CSS**:
```css
.form-group {
  margin-bottom: var(--space-6);
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--gray-700);
  margin-bottom: var(--space-2);
}

.required {
  color: var(--accent-danger);
}

.form-control {
  display: block;
  width: 100%;
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-base);
  color: var(--gray-900);
  background: white;
  border: 2px solid var(--gray-300);
  border-radius: var(--radius-md);
  transition: all 0.15s ease;
}

.form-control:focus {
  outline: none;
  border-color: var(--pru-red);
  box-shadow: 0 0 0 3px var(--pru-red-lighter);
}

.form-control::placeholder {
  color: var(--gray-400);
}

.form-help {
  display: block;
  font-size: var(--text-xs);
  color: var(--gray-500);
  margin-top: var(--space-2);
}

.form-group.has-error .form-control {
  border-color: var(--accent-danger);
}

.form-group.has-error .form-control:focus {
  box-shadow: 0 0 0 3px rgba(230, 57, 70, 0.1);
}

.form-error {
  display: block;
  font-size: var(--text-xs);
  color: var(--accent-danger);
  margin-top: var(--space-2);
}

.form-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.form-checkbox input[type="checkbox"] {
  width: 20px;
  height: 20px;
  border: 2px solid var(--gray-300);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.form-checkbox label {
  font-size: var(--text-sm);
  color: var(--gray-700);
  cursor: pointer;
}
```

### 4. Badges & Tags

```html
<span class="badge badge-success">Completed</span>
<span class="badge badge-warning">In Progress</span>
<span class="badge badge-danger">Overdue</span>
<span class="badge badge-info">Assigned</span>

<span class="tag">Sales Skills</span>
<span class="tag">Product Knowledge</span>
```

**CSS**:
```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-full);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.badge-success {
  background: var(--accent-success);
  color: white;
}

.badge-warning {
  background: var(--accent-warning);
  color: var(--gray-900);
}

.badge-danger {
  background: var(--accent-danger);
  color: white;
}

.badge-info {
  background: var(--accent-info);
  color: white;
}

.tag {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  background: var(--gray-100);
  color: var(--gray-700);
  border-radius: var(--radius-sm);
  border: 1px solid var(--gray-200);
}
```

### 5. Timeline

```html
<div class="pru-timeline">
  <div class="timeline-item completed">
    <div class="timeline-marker">
      <span class="icon">✓</span>
    </div>
    <div class="timeline-content">
      <div class="timeline-header">
        <h4 class="timeline-title">Foundation Skills</h4>
        <span class="timeline-date">Completed Jan 15, 2025</span>
      </div>
      <p class="timeline-description">
        Basic sales techniques and product knowledge
      </p>
      <div class="timeline-meta">
        <span class="badge badge-success">100%</span>
        <span>5 courses • 12 hours</span>
      </div>
    </div>
  </div>

  <div class="timeline-item in-progress">
    <div class="timeline-marker">
      <span class="icon">⏱</span>
    </div>
    <div class="timeline-content">
      <div class="timeline-header">
        <h4 class="timeline-title">Advanced Sales Techniques</h4>
        <span class="timeline-date">In progress</span>
      </div>
      <p class="timeline-description">
        Consultative selling and objection handling
      </p>
      <div class="timeline-meta">
        <span class="badge badge-warning">60%</span>
        <span>3 of 5 courses • 6 of 10 hours</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" style="width: 60%"></div>
      </div>
    </div>
  </div>

  <div class="timeline-item pending">
    <div class="timeline-marker">
      <span class="icon">○</span>
    </div>
    <div class="timeline-content">
      <div class="timeline-header">
        <h4 class="timeline-title">Leadership Training</h4>
        <span class="timeline-date">Starts after completion</span>
      </div>
      <p class="timeline-description">
        Team management and coaching skills
      </p>
      <div class="timeline-meta">
        <span>8 courses • 20 hours</span>
      </div>
    </div>
  </div>
</div>
```

**CSS**:
```css
.pru-timeline {
  position: relative;
  padding-left: var(--space-8);
}

.pru-timeline::before {
  content: '';
  position: absolute;
  left: 16px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--gray-200);
}

.timeline-item {
  position: relative;
  padding-bottom: var(--space-8);
}

.timeline-marker {
  position: absolute;
  left: -28px;
  top: 4px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 3px solid var(--gray-300);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  z-index: 1;
}

.timeline-item.completed .timeline-marker {
  background: var(--accent-success);
  border-color: var(--accent-success);
  color: white;
}

.timeline-item.in-progress .timeline-marker {
  background: var(--accent-warning);
  border-color: var(--accent-warning);
  color: white;
  animation: pulse 2s infinite;
}

.timeline-item.pending .timeline-marker {
  background: white;
  border-color: var(--gray-300);
  color: var(--gray-400);
}

.timeline-content {
  background: white;
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--gray-200);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--space-2);
}

.timeline-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--gray-900);
}

.timeline-date {
  font-size: var(--text-xs);
  color: var(--gray-500);
}

.timeline-description {
  font-size: var(--text-sm);
  color: var(--gray-600);
  margin-bottom: var(--space-3);
}

.timeline-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-sm);
  color: var(--gray-600);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
```

### 6. Capability Heatmap

```html
<div class="pru-heatmap-container">
  <table class="pru-heatmap">
    <thead>
      <tr>
        <th class="heatmap-header-sticky">Agent</th>
        <th>Product Knowledge</th>
        <th>Sales Skills</th>
        <th>Customer Service</th>
        <th>Compliance</th>
        <th>Overall</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="heatmap-name">Nguyen Van A</td>
        <td class="heatmap-cell level-4">
          <div class="cell-content">
            <span class="cell-value">Expert</span>
            <span class="cell-score">92%</span>
          </div>
        </td>
        <td class="heatmap-cell level-3">
          <div class="cell-content">
            <span class="cell-value">Advanced</span>
            <span class="cell-score">78%</span>
          </div>
        </td>
        <td class="heatmap-cell level-4">
          <div class="cell-content">
            <span class="cell-value">Expert</span>
            <span class="cell-score">88%</span>
          </div>
        </td>
        <td class="heatmap-cell level-2">
          <div class="cell-content">
            <span class="cell-value">Intermediate</span>
            <span class="cell-score">65%</span>
          </div>
        </td>
        <td class="heatmap-cell level-3">
          <div class="cell-content">
            <span class="cell-value">Advanced</span>
            <span class="cell-score">81%</span>
          </div>
        </td>
      </tr>
      <!-- More rows... -->
    </tbody>
  </table>
</div>
```

**CSS**:
```css
.pru-heatmap-container {
  overflow-x: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--gray-200);
}

.pru-heatmap {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.pru-heatmap th {
  background: var(--gray-50);
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-weight: var(--font-semibold);
  color: var(--gray-700);
  border-bottom: 2px solid var(--gray-200);
  white-space: nowrap;
}

.heatmap-header-sticky {
  position: sticky;
  left: 0;
  z-index: 10;
  background: var(--gray-50);
}

.pru-heatmap td {
  padding: 0;
  border-bottom: 1px solid var(--gray-200);
}

.heatmap-name {
  padding: var(--space-3) var(--space-4);
  font-weight: var(--font-medium);
  color: var(--gray-900);
  position: sticky;
  left: 0;
  background: white;
  z-index: 5;
}

.heatmap-cell {
  padding: var(--space-3) var(--space-4);
  text-align: center;
  transition: all 0.2s;
}

.heatmap-cell:hover {
  transform: scale(1.05);
  z-index: 1;
  box-shadow: var(--shadow-lg);
}

.cell-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.cell-value {
  font-weight: var(--font-semibold);
}

.cell-score {
  font-size: var(--text-xs);
  opacity: 0.8;
}

/* Capability Levels */
.heatmap-cell.level-1 {
  background: #FEE2E2;
  color: #991B1B;
}

.heatmap-cell.level-2 {
  background: #FEF3C7;
  color: #92400E;
}

.heatmap-cell.level-3 {
  background: #DBEAFE;
  color: #1E40AF;
}

.heatmap-cell.level-4 {
  background: #D1FAE5;
  color: #065F46;
}
```

### 7. AI Chatbot Widget

```html
<div class="pru-chatbot-widget" data-state="collapsed">
  <!-- Trigger Button (Collapsed State) -->
  <button class="chatbot-trigger" onclick="toggleChatbot()">
    <span class="trigger-icon">💬</span>
    <span class="trigger-badge">3</span>
  </button>

  <!-- Chat Panel (Expanded State) -->
  <div class="chatbot-panel">
    <div class="chatbot-header">
      <div class="header-left">
        <span class="header-icon">🤖</span>
        <div class="header-text">
          <h3 class="header-title">Sales Assistant</h3>
          <span class="header-status online">Online</span>
        </div>
      </div>
      <button class="header-action" onclick="minimizeChatbot()">_</button>
      <button class="header-action" onclick="closeChatbot()">×</button>
    </div>

    <div class="chatbot-messages">
      <!-- Bot Message -->
      <div class="message message-bot">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="message-bubble">
            <p>Xin chào! Tôi có thể giúp gì cho bạn hôm nay?</p>
            <p>(Hello! How can I help you today?)</p>
          </div>
          <div class="message-time">10:32 AM</div>
        </div>
      </div>

      <!-- User Message -->
      <div class="message message-user">
        <div class="message-content">
          <div class="message-bubble">
            <p>How do I handle price objections?</p>
          </div>
          <div class="message-time">10:33 AM</div>
        </div>
        <div class="message-avatar">👤</div>
      </div>

      <!-- Bot Response with Sources -->
      <div class="message message-bot">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="message-bubble">
            <p>Great question! Here are proven techniques for handling price objections:</p>
            <ol>
              <li><strong>Value reframing</strong>: Shift focus from price to value</li>
              <li><strong>Break it down</strong>: Show cost per day/month</li>
              <li><strong>Comparison</strong>: Compare to competitor products</li>
            </ol>
          </div>
          <div class="message-sources">
            <span class="sources-label">Sources:</span>
            <a href="#" class="source-link">Sales Training Manual (p.42)</a>
            <a href="#" class="source-link">Objection Handling Guide</a>
          </div>
          <div class="message-time">10:33 AM</div>
          <div class="message-actions">
            <button class="message-action" title="Helpful">👍</button>
            <button class="message-action" title="Not helpful">👎</button>
            <button class="message-action" title="Copy">📋</button>
          </div>
        </div>
      </div>

      <!-- Typing Indicator -->
      <div class="message message-bot typing">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="message-bubble">
            <div class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Suggested Questions -->
    <div class="chatbot-suggestions">
      <button class="suggestion-chip">How to close a sale?</button>
      <button class="suggestion-chip">Product comparison</button>
      <button class="suggestion-chip">Regulatory requirements</button>
    </div>

    <div class="chatbot-input">
      <button class="input-action" title="Attach file">📎</button>
      <input
        type="text"
        class="input-field"
        placeholder="Ask me anything about sales..."
        onkeypress="handleKeyPress(event)"
      />
      <button class="input-send" onclick="sendMessage()">
        <span>➤</span>
      </button>
    </div>
  </div>
</div>
```

**CSS** (continued in next section due to length):
```css
.pru-chatbot-widget {
  position: fixed;
  bottom: var(--space-6);
  right: var(--space-6);
  z-index: 9999;
}

/* Trigger Button */
.chatbot-trigger {
  width: 64px;
  height: 64px;
  background: var(--pru-red);
  color: white;
  border: none;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-lg);
  cursor: pointer;
  position: relative;
  transition: all 0.3s ease;
}

.chatbot-trigger:hover {
  transform: scale(1.1);
  box-shadow: var(--shadow-xl);
}

.trigger-icon {
  font-size: 32px;
}

.trigger-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: var(--accent-danger);
  color: white;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid white;
}

/* Chat Panel */
.chatbot-panel {
  display: none;
  flex-direction: column;
  width: 380px;
  height: 600px;
  background: white;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-2xl);
  overflow: hidden;
}

.pru-chatbot-widget[data-state="expanded"] .chatbot-trigger {
  display: none;
}

.pru-chatbot-widget[data-state="expanded"] .chatbot-panel {
  display: flex;
}

/* Header */
.chatbot-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--pru-red);
  color: white;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 1;
}

.header-icon {
  font-size: 24px;
}

.header-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  margin: 0;
}

.header-status {
  font-size: var(--text-xs);
  opacity: 0.9;
}

.header-status.online::before {
  content: '●';
  margin-right: var(--space-1);
  color: var(--accent-success);
}

.header-action {
  width: 32px;
  height: 32px;
  background: rgba(255,255,255,0.2);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 20px;
  cursor: pointer;
  transition: background 0.2s;
}

.header-action:hover {
  background: rgba(255,255,255,0.3);
}

/* Messages */
.chatbot-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  background: var(--gray-50);
}

.message {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.message-bot {
  flex-direction: row;
}

.message-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: var(--gray-200);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-content {
  flex: 1;
  max-width: 75%;
}

.message-bubble {
  background: white;
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.message-user .message-bubble {
  background: var(--pru-red);
  color: white;
}

.message-bubble p {
  margin: 0 0 var(--space-2) 0;
}

.message-bubble p:last-child {
  margin-bottom: 0;
}

.message-bubble ol, .message-bubble ul {
  margin: var(--space-2) 0;
  padding-left: var(--space-5);
}

.message-bubble li {
  margin-bottom: var(--space-1);
}

.message-time {
  font-size: var(--text-xs);
  color: var(--gray-500);
  margin-top: var(--space-1);
}

.message-sources {
  margin-top: var(--space-2);
  padding: var(--space-2);
  background: var(--gray-100);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
}

.sources-label {
  font-weight: var(--font-semibold);
  color: var(--gray-700);
  margin-right: var(--space-2);
}

.source-link {
  display: inline-block;
  color: var(--pru-red);
  text-decoration: none;
  margin-right: var(--space-2);
}

.source-link:hover {
  text-decoration: underline;
}

.message-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.message-action {
  width: 28px;
  height: 28px;
  background: white;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
}

.message-action:hover {
  background: var(--gray-100);
  transform: scale(1.1);
}

/* Typing Indicator */
.typing-dots {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: var(--space-2) 0;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  background: var(--gray-400);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-8px);
  }
}

/* Suggestions */
.chatbot-suggestions {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  overflow-x: auto;
  border-top: 1px solid var(--gray-200);
}

.suggestion-chip {
  padding: var(--space-2) var(--space-3);
  background: white;
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-chip:hover {
  background: var(--pru-red-lighter);
  border-color: var(--pru-red);
  color: var(--pru-red-dark);
}

/* Input */
.chatbot-input {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-top: 1px solid var(--gray-200);
  background: white;
}

.input-action {
  width: 36px;
  height: 36px;
  background: transparent;
  border: none;
  font-size: 18px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.input-action:hover {
  opacity: 0.7;
}

.input-field {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  outline: none;
}

.input-field:focus {
  border-color: var(--pru-red);
}

.input-send {
  width: 36px;
  height: 36px;
  background: var(--pru-red);
  color: white;
  border: none;
  border-radius: var(--radius-full);
  font-size: 18px;
  cursor: pointer;
  transition: background 0.2s;
}

.input-send:hover {
  background: var(--pru-red-dark);
}

/* Mobile Responsive */
@media (max-width: 480px) {
  .chatbot-panel {
    position: fixed;
    bottom: 0;
    right: 0;
    left: 0;
    width: 100%;
    height: 100%;
    max-height: 100vh;
    border-radius: 0;
  }

  .pru-chatbot-widget {
    bottom: var(--space-4);
    right: var(--space-4);
  }
}
```

---

## Mobile PWA Design

### Bottom Navigation

```html
<nav class="pru-mobile-nav">
  <a href="/dashboard" class="nav-item active">
    <span class="nav-icon">📊</span>
    <span class="nav-label">Dashboard</span>
  </a>
  <a href="/learning" class="nav-item">
    <span class="nav-icon">📚</span>
    <span class="nav-label">Learning</span>
  </a>
  <a href="/coaching" class="nav-item">
    <span class="nav-icon">🎯</span>
    <span class="nav-label">Coaching</span>
    <span class="nav-badge">2</span>
  </a>
  <a href="/chat" class="nav-item">
    <span class="nav-icon">💬</span>
    <span class="nav-label">AI Chat</span>
  </a>
  <a href="/profile" class="nav-item">
    <span class="nav-icon">👤</span>
    <span class="nav-label">Profile</span>
  </a>
</nav>
```

**CSS**:
```css
.pru-mobile-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: white;
  border-top: 1px solid var(--gray-200);
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  padding: var(--space-2) 0;
  z-index: 1000;
  safe-area-inset-bottom: env(safe-area-inset-bottom);
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2);
  text-decoration: none;
  color: var(--gray-600);
  transition: color 0.2s;
  position: relative;
}

.nav-item.active {
  color: var(--pru-red);
}

.nav-icon {
  font-size: 24px;
}

.nav-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.nav-badge {
  position: absolute;
  top: 4px;
  right: 16px;
  background: var(--pru-red);
  color: white;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Active state indicator */
.nav-item::before {
  content: '';
  position: absolute;
  top: -2px;
  left: 50%;
  transform: translateX(-50%);
  width: 32px;
  height: 3px;
  background: var(--pru-red);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  opacity: 0;
  transition: opacity 0.2s;
}

.nav-item.active::before {
  opacity: 1;
}
```

---

## Responsive Design Guidelines

### Breakpoints

```css
/* Mobile (default) */
/* 0-639px */

/* Tablet */
@media (min-width: 640px) {
  /* sm: tablets in portrait */
}

/* Desktop */
@media (min-width: 1024px) {
  /* lg: laptops */
  .pru-mobile-nav { display: none; } /* Hide mobile nav */
}

/* Large Desktop */
@media (min-width: 1280px) {
  /* xl: desktops */
}
```

### Touch Targets

- Minimum size: **44×44px** (WCAG AAA)
- Recommended: **48×48px**
- Spacing between targets: **8px minimum**

### Responsive Layout Patterns

**Stack → Side-by-side**:
```css
.container {
  display: flex;
  flex-direction: column; /* Mobile: stacked */
  gap: var(--space-4);
}

@media (min-width: 1024px) {
  .container {
    flex-direction: row; /* Desktop: side-by-side */
  }
}
```

---

## Accessibility Guidelines

### Color Contrast

All text must meet **WCAG 2.1 AA** standards:
- Normal text (< 18px): **4.5:1** contrast ratio
- Large text (≥ 18px or ≥ 14px bold): **3:1** contrast ratio

**Verified Combinations**:
- ✅ `--gray-900` on `white` (16.1:1)
- ✅ `--gray-700` on `white` (10.4:1)
- ✅ `white` on `--pru-red` (4.8:1)
- ✅ `white` on `--pru-blue` (10.2:1)

### Keyboard Navigation

- All interactive elements must be keyboard accessible
- Visible focus indicators (`:focus` states)
- Logical tab order
- Skip links for main content

```css
*:focus {
  outline: 2px solid var(--pru-red);
  outline-offset: 2px;
}

button:focus,
a:focus {
  box-shadow: 0 0 0 3px var(--pru-red-lighter);
}
```

### Screen Reader Support

```html
<!-- Proper ARIA labels -->
<button aria-label="Close chat">×</button>

<!-- Hidden text for icons -->
<button>
  <span aria-hidden="true">🔔</span>
  <span class="sr-only">View notifications</span>
</button>

<!-- Loading states -->
<div role="status" aria-live="polite">
  <span class="spinner" aria-hidden="true"></span>
  <span class="sr-only">Loading...</span>
</div>
```

```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0,0,0,0);
  white-space: nowrap;
  border-width: 0;
}
```

---

## Animation Guidelines

### Performance

Use GPU-accelerated properties:
- ✅ `transform`
- ✅ `opacity`
- ❌ Avoid: `width`, `height`, `top`, `left`

### Duration

```css
--duration-fast: 150ms;    /* Micro-interactions */
--duration-base: 250ms;    /* Standard transitions */
--duration-slow: 400ms;    /* Complex animations */
```

### Easing

```css
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Design Checklist

Before launching:

### Visual Design
- [ ] Brand colors consistent throughout
- [ ] Typography scale applied consistently
- [ ] Spacing system used (no arbitrary values)
- [ ] Border radius consistent
- [ ] Shadows consistent
- [ ] All icons same style (outline vs solid)

### Responsive
- [ ] Mobile design (320px+)
- [ ] Tablet design (768px+)
- [ ] Desktop design (1024px+)
- [ ] Touch targets ≥ 44px on mobile
- [ ] No horizontal scrolling

### Accessibility
- [ ] Color contrast ≥ 4.5:1 (normal text)
- [ ] Color contrast ≥ 3:1 (large text)
- [ ] All images have alt text
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] ARIA labels where needed
- [ ] Screen reader tested

### Performance
- [ ] Images optimized (WebP, lazy loading)
- [ ] Animations use transform/opacity
- [ ] No layout shifts (CLS)
- [ ] Loading states for async operations
- [ ] Skeleton screens for initial load

### Usability
- [ ] Clear call-to-action buttons
- [ ] Error messages helpful
- [ ] Success confirmations visible
- [ ] Empty states designed
- [ ] Loading states designed
- [ ] Tooltips for complex UI

---

**Document Version**: 1.0
**Last Updated**: October 27, 2025
**Status**: Design System Ready for Implementation
