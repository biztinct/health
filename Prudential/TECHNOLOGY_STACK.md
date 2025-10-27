# PruLearn360 - Technology Stack Documentation

## Overview

Complete technology stack for PruLearn360 - all components are **100% free and open source** with no licensing costs.

---

## Backend Technology Stack

### Core Framework

**Odoo 18 Community Edition**
- **Version**: 18.0 (October 2024 release)
- **Language**: Python 3.10+
- **License**: LGPL-3
- **Why**: Mature enterprise framework, existing healthcare system compatibility
- **URL**: https://github.com/odoo/odoo

### Database

**PostgreSQL 15**
- **Version**: 15.x (latest stable)
- **License**: PostgreSQL License (permissive)
- **Why**: Odoo native support, enterprise reliability, JSON support
- **Features**: Full-text search, JSONB, materialized views, table partitioning
- **URL**: https://www.postgresql.org/

### Cache & Queue

**Redis 7**
- **Version**: 7.2.x
- **License**: BSD-3-Clause
- **Why**: Fast in-memory cache, pub/sub for real-time features, Celery backend
- **Use cases**: Session storage, Celery broker, real-time notifications
- **URL**: https://redis.io/

**Celery**
- **Version**: 5.3.x
- **Language**: Python
- **License**: BSD
- **Why**: Distributed task queue for background jobs (data sync, email sending)
- **URL**: https://docs.celeryq.dev/

---

## AI & Machine Learning Stack

### Large Language Model (LLM)

**Llama 3.2 (Meta AI)**
- **Model**: llama3.2:8b (8 billion parameters)
- **Deployment**: Via Ollama
- **License**: Llama 3 Community License (free for commercial use)
- **Why**: State-of-the-art open model, runs locally (no API costs), data privacy
- **Requirements**: 16GB RAM, GPU optional (speeds up inference)
- **URL**: https://ollama.com/library/llama3.2

**Ollama**
- **Version**: Latest
- **License**: MIT
- **Why**: Easy local LLM deployment, API-compatible with OpenAI format
- **Features**: Model management, GPU acceleration, concurrent requests
- **URL**: https://ollama.com/

### RAG Framework

**LlamaIndex**
- **Version**: 0.10.x
- **Language**: Python
- **License**: MIT
- **Why**: Superior retrieval strategies, enterprise-ready, great documentation
- **Features**: Multiple data connectors, query engines, evaluation tools
- **URL**: https://www.llamaindex.ai/

**Alternatives Considered**:
- LangChain (more complex, overlapping features)
- Haystack (NLP-focused, less flexible for custom workflows)

### Vector Database

**ChromaDB**
- **Version**: 0.4.x
- **Language**: Python
- **License**: Apache-2.0
- **Why**: Lightweight, Python-native, easy deployment, no separate server
- **Features**: Persistent storage, metadata filtering, similarity search
- **URL**: https://www.trychroma.com/

**Alternatives Considered**:
- Pinecone (commercial, cloud-only)
- Weaviate (requires separate deployment, heavier)
- Qdrant (good but more complex setup)

### Embeddings

**sentence-transformers**
- **Model**: `paraphrase-multilingual-MiniLM-L12-v2`
- **License**: Apache-2.0
- **Why**: Multilingual support (Vietnamese + English), 384 dimensions (fast), good quality
- **Features**: Pre-trained on 50+ languages, efficient inference
- **URL**: https://www.sbert.net/

**Alternative Models**:
- `all-MiniLM-L6-v2` (English-only, faster)
- `multilingual-e5-large` (larger, more accurate, slower)

---

## Business Intelligence & Analytics

### BI Tool

**Metabase**
- **Version**: v0.48.x (latest open source)
- **License**: AGPL (open source edition)
- **Language**: Clojure (JVM)
- **Why**: User-friendly UI, JWT embedding support, no SQL required for basic queries
- **Features**: 40+ visualization types, dashboard builder, SQL editor, embedding
- **URL**: https://www.metabase.com/

**Setup**:
```bash
docker run -d -p 3000:3000 \
  --name metabase \
  -e "MB_DB_TYPE=postgres" \
  -e "MB_DB_DBNAME=metabase" \
  -e "MB_DB_PORT=5432" \
  -e "MB_DB_USER=metabase" \
  -e "MB_DB_PASS=SecurePassword" \
  -e "MB_DB_HOST=postgres" \
  metabase/metabase:latest
```

**Alternatives Considered**:
- Apache Superset (more complex setup, requires Celery + Redis for async)
- Grafana (better for time-series, less suited for business metrics)
- Redash (simpler but less polished UI)

### Charting Libraries (Frontend)

**Chart.js**
- **Version**: 4.x
- **License**: MIT
- **Why**: Simple, lightweight, responsive, good documentation
- **Use cases**: Simple line/bar/pie charts in Odoo views
- **URL**: https://www.chartjs.org/

**Apache ECharts**
- **Version**: 5.x
- **License**: Apache-2.0
- **Why**: Advanced visualizations (heatmaps, gauges, sankey), highly customizable
- **Use cases**: Capability heatmaps, complex dashboards
- **URL**: https://echarts.apache.org/

---

## Frontend Technology Stack

### Web Framework (Odoo)

**OWL (Odoo Web Library)**
- **Version**: 2.x (Odoo 18 native)
- **Language**: JavaScript
- **Why**: Odoo's native reactive framework, lightweight, Vue-like syntax
- **Features**: Components, hooks, reactive state
- **URL**: https://github.com/odoo/owl

**JavaScript ES6+**
- Modern JavaScript (async/await, arrow functions, modules)
- No transpilation needed for modern browsers

### Mobile PWA Framework

**Vue.js 3**
- **Version**: 3.4.x
- **License**: MIT
- **Why**: Lightweight, great developer experience, Composition API
- **Features**: Reactive state, component-based, TypeScript support
- **URL**: https://vuejs.org/

**Quasar Framework**
- **Version**: 2.x
- **License**: MIT
- **Why**: Material Design components, PWA builder, cross-platform (web/mobile/desktop)
- **Features**: 100+ components, CLI, PWA mode, responsive out-of-box
- **URL**: https://quasar.dev/

**Pinia (State Management)**
- **Version**: 2.x
- **License**: MIT
- **Why**: Official Vue 3 state management (replaces Vuex), simpler API
- **URL**: https://pinia.vuejs.org/

**Vue Router**
- **Version**: 4.x
- **License**: MIT
- **Why**: Official routing for Vue 3, lazy loading, navigation guards
- **URL**: https://router.vuejs.org/

### Build Tools

**Vite**
- **Version**: 5.x
- **License**: MIT
- **Why**: Fast HMR (Hot Module Replacement), modern build tool, Vue 3 native
- **URL**: https://vitejs.dev/

**PostCSS + Autoprefixer**
- Auto-prefix CSS for cross-browser compatibility

### CSS Framework

**Tailwind CSS**
- **Version**: 3.x
- **License**: MIT
- **Why**: Utility-first, highly customizable, modern design patterns
- **Features**: JIT compiler, responsive variants, dark mode
- **URL**: https://tailwindcss.com/

**Custom Design System**: Prudential branding colors, components

### Offline Storage

**PouchDB**
- **Version**: 8.x
- **License**: Apache-2.0
- **Why**: Client-side database, CouchDB sync, offline-first, IndexedDB backend
- **Features**: Replication, conflict resolution, attachments
- **URL**: https://pouchdb.com/

**IndexedDB** (via PouchDB adapter)
- Browser native storage (50MB+ quota)

### Service Worker

**Workbox**
- **Version**: 7.x
- **License**: Apache-2.0 (Google)
- **Why**: Service worker helpers, caching strategies, background sync
- **URL**: https://developer.chrome.com/docs/workbox/

---

## Integration & API Stack

### HTTP Client

**Axios**
- **Version**: 1.x
- **License**: MIT
- **Why**: Promise-based, interceptors, timeout support, browser + Node.js
- **URL**: https://axios-http.com/

**Python Requests**
- **Version**: 2.31.x
- **License**: Apache-2.0
- **Why**: Simple API, session support, excellent for REST API consumption
- **URL**: https://requests.readthedocs.io/

### API Authentication

**JWT (JSON Web Tokens)**
- **Library**: PyJWT (Python), jsonwebtoken (JavaScript)
- **Why**: Stateless authentication, secure token-based auth
- **Use cases**: Metabase embedding, API authentication

**OAuth2**
- **Library**: Authlib (Python)
- **Why**: Standard protocol for Docebo API integration

---

## DevOps & Infrastructure

### Containerization

**Docker**
- **Version**: 24.x
- **License**: Apache-2.0
- **Why**: Consistent environments, easy deployment, isolation
- **URL**: https://www.docker.com/

**Docker Compose**
- **Version**: 2.x
- **Why**: Multi-container orchestration, dev environment setup
- **URL**: https://docs.docker.com/compose/

### Web Server

**Nginx**
- **Version**: 1.25.x
- **License**: BSD
- **Why**: High performance, reverse proxy, SSL termination, static file serving
- **URL**: https://nginx.org/

### SSL/TLS

**Let's Encrypt**
- **Tool**: Certbot
- **License**: Free, automated
- **Why**: Free SSL certificates, auto-renewal
- **URL**: https://letsencrypt.org/

### Monitoring (Optional)

**Prometheus**
- **License**: Apache-2.0
- **Why**: Time-series metrics database, powerful query language
- **URL**: https://prometheus.io/

**Grafana**
- **License**: AGPL
- **Why**: Beautiful dashboards, alerting, Prometheus integration
- **URL**: https://grafana.com/

**Loki** (Log aggregation)
- **License**: AGPL
- **Why**: Log collection, integration with Grafana
- **URL**: https://grafana.com/oss/loki/

---

## Development Tools

### Version Control

**Git**
- Standard version control
- GitHub/GitLab for repository hosting

### Code Quality

**Black** (Python formatter)
- **License**: MIT
- **Why**: Opinionated code formatting, PEP 8 compliant

**Pylint** (Python linter)
- **License**: GPL
- **Why**: Code analysis, error detection

**ESLint** (JavaScript linter)
- **License**: MIT
- **Why**: Code quality, best practices enforcement

**Prettier** (JavaScript/CSS formatter)
- **License**: MIT
- **Why**: Consistent code formatting

### Testing

**pytest** (Python testing)
- **License**: MIT
- **Why**: Simple syntax, powerful fixtures, Odoo compatible

**Vitest** (Vue.js testing)
- **License**: MIT
- **Why**: Fast, Vite-native, Jest-compatible API

**Playwright** (E2E testing)
- **License**: Apache-2.0
- **Why**: Cross-browser automation, modern API
- **URL**: https://playwright.dev/

### API Testing

**Postman/Insomnia**
- REST API testing and documentation

---

## Python Packages

### Core Odoo Dependencies
```
# Core framework
odoo==18.0
psycopg2-binary>=2.9.5  # PostgreSQL adapter
python-dateutil>=2.8.2
lxml>=4.9.2
Pillow>=10.0.0
reportlab>=4.0.4
zeep>=4.2.1  # SOAP client (if needed)
num2words>=0.5.12
chardet>=5.1.0
passlib>=1.7.4
```

### AI & ML Packages
```
# LLM & RAG
llama-index>=0.10.0
llama-index-vector-stores-chroma>=0.1.0
llama-index-llms-ollama>=0.1.0
chromadb>=0.4.18
sentence-transformers>=2.2.2

# Document processing
pypdf2>=3.0.1
python-docx>=0.8.11
python-pptx>=0.6.21

# Alternative LLM libraries (optional)
langchain>=0.1.0  # If needed for specific features
transformers>=4.35.0  # HuggingFace models
torch>=2.1.0  # For local model inference
```

### API Integration
```
requests>=2.31.0
authlib>=1.2.1  # OAuth2
pyjwt>=2.8.0  # JWT tokens
httpx>=0.25.0  # Async HTTP (optional)
```

### Task Queue
```
celery>=5.3.4
redis>=5.0.1
kombu>=5.3.4  # Celery messaging
```

### Data Processing
```
pandas>=2.1.3  # Data analysis (optional for reporting)
numpy>=1.26.2  # Numerical computing
```

### Utilities
```
python-dotenv>=1.0.0  # Environment variables
pytz>=2023.3  # Timezone support
```

---

## JavaScript/Node.js Packages

### Vue.js PWA Dependencies
```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.5",
    "pinia": "^2.1.7",
    "quasar": "^2.14.0",
    "@quasar/extras": "^1.16.9",
    "axios": "^1.6.2",
    "pouchdb": "^8.0.1",
    "pouchdb-find": "^8.0.1",
    "chart.js": "^4.4.1",
    "vue-chartjs": "^5.3.0",
    "date-fns": "^2.30.0",
    "tailwindcss": "^3.4.0"
  },
  "devDependencies": {
    "vite": "^5.0.10",
    "@vitejs/plugin-vue": "^5.0.2",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "eslint": "^8.56.0",
    "prettier": "^3.1.1",
    "vitest": "^1.1.0",
    "@vue/test-utils": "^2.4.3"
  }
}
```

### Odoo OWL (No npm needed)
- Bundled with Odoo 18
- ES6 modules loaded via Odoo asset bundles

---

## Database Schema Tools

**pgAdmin 4** (optional GUI)
- **License**: PostgreSQL License
- **Why**: Database management, query optimization
- **URL**: https://www.pgadmin.org/

**DBeaver** (universal database tool)
- **License**: Apache-2.0
- **Why**: Cross-platform, supports many databases, ER diagrams
- **URL**: https://dbeaver.io/

---

## Recommended Development Environment

### IDE/Editor

**Visual Studio Code**
- **License**: MIT
- **Extensions**:
  - Python (Microsoft)
  - Pylance
  - Odoo Snippets
  - Volar (Vue 3)
  - ESLint
  - Prettier
  - Tailwind CSS IntelliSense
  - GitLens
  - Docker

**PyCharm Community Edition** (alternative)
- **License**: Apache-2.0
- **Why**: Best Python IDE, Odoo plugin available

### Operating System

**Development**: macOS, Linux (Ubuntu 22.04 LTS), Windows (WSL2)
**Production**: Linux (Ubuntu 22.04 LTS Server, Debian 12)

---

## Deployment Architecture

### Recommended Stack

```
┌─────────────────────────────────────────────┐
│           Internet (HTTPS/443)               │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│         Nginx (Reverse Proxy + SSL)         │
│  • Let's Encrypt SSL                        │
│  • Load balancing (if multi-server)         │
│  • Static file serving                      │
└───────────────────┬─────────────────────────┘
                    │
        ┌───────────┴──────────┬──────────────┐
        │                      │              │
┌───────▼──────┐     ┌────────▼────┐   ┌─────▼──────┐
│ Odoo 18 CE   │     │ Metabase    │   │ Ollama     │
│ (8 workers)  │     │ (BI)        │   │ (Llama 3)  │
│ Port 8069    │     │ Port 3000   │   │ Port 11434 │
└───────┬──────┘     └─────────────┘   └────────────┘
        │
┌───────▼────────────────────────────────────┐
│        PostgreSQL 15 (Port 5432)           │
│  • Odoo database                           │
│  • Metabase database (separate)            │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│           Redis 7 (Port 6379)              │
│  • Session cache                           │
│  • Celery broker                           │
└───────────────────┬────────────────────────┘
                    │
┌───────────────────▼────────────────────────┐
│        Celery Workers (Background)         │
│  • Data sync (Docebo, PD Platform)         │
│  • Email sending                           │
│  • Report generation                       │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│          ChromaDB (Local Storage)          │
│  • Vector embeddings                       │
│  • Knowledge base                          │
└────────────────────────────────────────────┘
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: SecurePassword
      POSTGRES_DB: prulearn360
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    restart: always

  odoo:
    image: odoo:18.0
    depends_on:
      - postgres
      - redis
    environment:
      - HOST=postgres
      - USER=odoo
      - PASSWORD=SecurePassword
    volumes:
      - odoo-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons
      - ./config:/etc/odoo
    ports:
      - "8069:8069"
    restart: always

  celery:
    image: odoo:18.0
    command: celery -A odoo worker -l info
    depends_on:
      - redis
      - postgres
    volumes:
      - ./addons:/mnt/extra-addons
    restart: always

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama-data:/root/.ollama
    ports:
      - "11434:11434"
    restart: always

  metabase:
    image: metabase/metabase:latest
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER: metabase
      MB_DB_PASS: SecurePassword
      MB_DB_HOST: postgres
    ports:
      - "3000:3000"
    depends_on:
      - postgres
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - ./nginx/static:/usr/share/nginx/html/static
    depends_on:
      - odoo
      - metabase
    restart: always

volumes:
  postgres-data:
  redis-data:
  odoo-data:
  ollama-data:
```

---

## Cost Summary

| Component | License | Monthly Cost |
|-----------|---------|--------------|
| Odoo 18 CE | LGPL-3 | $0 |
| PostgreSQL | PostgreSQL License | $0 |
| Redis | BSD | $0 |
| Llama 3 (Ollama) | Llama 3 License | $0 |
| LlamaIndex | MIT | $0 |
| ChromaDB | Apache-2.0 | $0 |
| Metabase | AGPL | $0 |
| Vue.js 3 | MIT | $0 |
| Quasar | MIT | $0 |
| Tailwind CSS | MIT | $0 |
| Nginx | BSD | $0 |
| Let's Encrypt | Free | $0 |
| Docker | Apache-2.0 | $0 |
| **Total Software** | | **$0** |
| **Infrastructure** (Hetzner CX41) | | **$55** |
| **Grand Total** | | **$55/month** |

---

## Version Compatibility Matrix

| Component | Minimum Version | Recommended | Notes |
|-----------|----------------|-------------|-------|
| Python | 3.10 | 3.11 | Odoo 18 requirement |
| PostgreSQL | 12 | 15 | Odoo supports 12+ |
| Redis | 6.0 | 7.2 | Celery compatible |
| Node.js | 18 | 20 LTS | For Vue.js build |
| npm | 9 | 10 | Package manager |
| Docker | 20.10 | 24.0 | Compose v2 |
| Nginx | 1.20 | 1.25 | HTTP/2 support |

---

## License Compliance

All components are **free for commercial use** with no licensing fees. Key licenses:

- **LGPL-3** (Odoo): Can be used commercially, modifications to Odoo core must be open-sourced
- **MIT** (Vue.js, Tailwind, etc.): Permissive, commercial use allowed
- **Apache-2.0** (ChromaDB, Docker): Permissive, patent grant
- **BSD** (Redis, Nginx): Very permissive
- **PostgreSQL License**: Very permissive, similar to MIT
- **Llama 3 License**: Free for commercial use, some restrictions on very large deployments (750M+ MAU)

**No proprietary licenses required** ✅

---

## Alternative Technology Considerations

### If Budget Allows (Commercial Options)

These are **NOT recommended** for initial implementation but listed for reference:

| Component | Commercial Alternative | Cost | Why Not Chosen |
|-----------|----------------------|------|----------------|
| LLM | OpenAI GPT-4 | $0.03/1k tokens | Data privacy, ongoing costs |
| LLM | Anthropic Claude | $0.015/1k tokens | Data privacy, ongoing costs |
| Vector DB | Pinecone | $70/month | Free alternatives sufficient |
| BI Tool | Tableau | $70/user/month | Metabase sufficient |
| BI Tool | Power BI | $10/user/month | Metabase more flexible |
| Hosting | AWS/GCP | $300+/month | Hetzner 5x cheaper |

**Savings by using open source**: **$10,000+/month** ($120k+/year)

---

## Documentation & Resources

### Official Documentation Links

- **Odoo**: https://www.odoo.com/documentation/18.0/
- **PostgreSQL**: https://www.postgresql.org/docs/15/
- **Vue.js**: https://vuejs.org/guide/
- **LlamaIndex**: https://docs.llamaindex.ai/
- **Metabase**: https://www.metabase.com/docs/
- **Quasar**: https://quasar.dev/docs
- **Tailwind CSS**: https://tailwindcss.com/docs

### Community Support

- **Odoo Community**: https://www.odoo.com/forum
- **Stack Overflow**: Active tags for all components
- **GitHub Discussions**: Most projects have active communities
- **Discord/Slack**: Many projects have community chat

---

## Conclusion

This technology stack provides:

✅ **Zero licensing costs** (100% free & open source)
✅ **Enterprise-grade reliability** (battle-tested components)
✅ **Modern development experience** (latest tools & frameworks)
✅ **Scalability** (horizontal scaling possible)
✅ **Data privacy** (local LLM, self-hosted)
✅ **Active communities** (long-term support)
✅ **Future-proof** (no vendor lock-in)

**Total technology cost**: **$0/month** (only infrastructure costs ~$55/month)

---

**Document Version**: 1.0
**Last Updated**: October 27, 2025
**Status**: Production-Ready Stack
