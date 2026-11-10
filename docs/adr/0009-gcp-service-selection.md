# ADR 0009: Вибір сервісів Google Cloud Platform (GCP) для міграції проєкту OneTwoThree / Spry

- **Статус:** Прийнято (Accepted)
- **Дата:** 2026-11-10
- **Контекст:** Лабораторна робота 9 — «One project, two clouds: Spry on Google Cloud»

---

## 1. Контекст і постановка задачі

Проєкт **OneTwoThree (Spry)** — це вебзастосунок для планування та керування зустрічами, створений на стеку **React (TypeScript/Vite)** + **FastAPI (Python 3.12, SQLAlchemy, Alembic)** + **PostgreSQL**. Початково система була спроєктована та розгорнута в хмарі **Amazon Web Services (AWS)** з використанням serverless- та контейнерних сервісів, керованих через Terraform (`infra/`).

У межах **Lab 9** перед командою стоїть завдання побудувати **другий хмарний контур на Google Cloud Platform (GCP)** у регіоні `us-central1` (Iowa), перенести ядро продукту (фронтенд, бекенд API та реляційну базу даних) під управління Terraform (`gcp/`), порівняти архітектурні компроміси обох хмар і провести точний фінансовий розрахунок (FinOps) вартості володіння (TCO) для чотирьох профілів трафіку.

Ключовий інженерний принцип цієї міграції: **ми переносимо архітектурні патерни (stateless-контейнери за HTTPS, керована БД, секрети поза кодом, Infrastructure as Code з найменшими привілеями), а не сліпо копіюємо імена сервісів AWS**.

---

## 2. Таблиця відповідності сервісів (AWS → Google Cloud)

Нижче наведено повну матрицю мапінгу компонентів нашої архітектури з AWS на еквіваленти Google Cloud Platform, включно з прийнятим рішенням для **Фази 1 (Core Migration)** та обґрунтуванням:

| Зона відповідальності | Поточний сервіс AWS (Labs 2–7) | Еквівалент Google Cloud Platform (GCP) | Рішення у Lab 9 (`Keep` / `Replace` / `Drop`) | Обґрунтування вибору для нашого проєкту |
| :--- | :--- | :--- | :--- | :--- |
| **Static Frontend & CDN** | **S3 + CloudFront (+ WAF)** | **Firebase Hosting** (або Cloud Storage + Cloud CDN) | **Replace → Firebase Hosting** | Firebase Hosting надає глобальний CDN, автоматичний SSL-сертифікат, миттєвий деплой (`firebase deploy --only hosting`), SPA-роутинг і головне — нативні `rewrites` префікса `/api/**` напряму в Cloud Run. Це дає **єдиний origin** без проблем із CORS і коштує **$0/міс** у межах Free Tier (10 GB storage, 360 MB/day transfer). |
| **Backend API Compute** | **AWS Lambda + Function URL** (або ECS Fargate) | **Cloud Run** | **Replace → Cloud Run** | Cloud Run — це стандарт для запуску stateless HTTP-контейнерів у GCP. На відміну від Lambda, він нативно запускає звичайний Docker-образ з `uvicorn` на порту `$PORT` (8080) **без AWS Lambda Web Adapter або Mangum**, підтримує конкурентні запити на один інстанс (до 80+), масштабується до нуля (`min_instance_count = 0`) і має щедрий безкоштовний ліміт (2 млн запитів, 180 000 vCPU-s, 360 000 GiB-s на місяць). |
| **Container Registry** | **Amazon ECR** | **Artifact Registry** | **Replace → Artifact Registry** | Керований Docker-реєстр у тому ж регіоні (`us-central1`), інтегрований із Cloud Build та Cloud Run через IAM. Перші **0.5 GB/міс — безкоштовні**. |
| **Relational Database** | **Aurora Serverless v2 (PostgreSQL)** (`0–1 ACU`) | **Cloud SQL for PostgreSQL** (`db-f1-micro`) або **AlloyDB** | **Replace → Cloud SQL (`db-f1-micro`)** | Дозволяє зберегти 100% коду моделей SQLAlchemy та міграцій Alembic (`alembic upgrade head`) без переписування бізнес-логіки. Cloud Run підключається до Cloud SQL через вбудований Cloud SQL Auth Proxy (Unix-сокет `/cloudsql/<CONNECTION_NAME>`). |
| **Document / NoSQL DB** | **Amazon DynamoDB** | **Cloud Firestore** | **Alternative / Stretch** | Повністю безсерверна документна БД з **Free Quota 50 000 reads/day та 20 000 writes/day ($0 у простої)**. Ідеальна за ціною, але вимагала б переписування реляційних SQLAlchemy-запитів та JOIN-ів на документну модель. |
| **User Authentication** | **Amazon Cognito User Pool + Google IdP** | **Identity Platform / Firebase Authentication** | **Defer (залишити в scope Фази 2)** | Firebase Auth / Identity Platform повністю сумісні зі стандартом OIDC/JWT і безкоштовні до 50 000 MAU. У Фазі 1 фокус на міграції Core API та БД; верифікація JWT легко перемикається зміною `JWKS_URL` та `ISSUER`. |
| **Scheduled Triggers** | **Amazon EventBridge Scheduler** | **Cloud Scheduler** | **Defer (Stretch goal)** | Cloud Scheduler надає 3 безкоштовні cron-завдання на місяць і вміє напряму викликати Cloud Run або публікувати в Pub/Sub з OIDC-токеном сервісного акаунта. |
| **Async Message Queue** | **Amazon SQS** | **Cloud Pub/Sub** (або **Cloud Tasks**) | **Defer (Stretch goal)** | Pub/Sub забезпечує асинхронну доставку повідомлень з push-підписками напряму в HTTP-ендпоінти Cloud Run (10 GB/міс безкоштовно). |
| **Object Storage Events** | **S3 Event Notification → Lambda** | **Cloud Storage + Eventarc → Cloud Run** | **Defer (Stretch goal)** | Eventarc транслює події створення об'єктів у Cloud Storage у стандартні CloudEvents HTTP POST запити до Cloud Run. |
| **Transactional Email** | **Amazon SES** | **Немає нативного сервісу GCP** (SendGrid / Mailgun / Resend або мультиклауд-виклик AWS SES) | **Replace → SendGrid API (або Keep AWS SES)** | У GCP відсутній власний сервіс транзакційної пошти. Стандартне рішення — зовнішній провайдер (SendGrid/Mailgun/Resend) або виклик AWS SES через HTTPS API, при цьому API-ключ зберігається у **GCP Secret Manager**. |
| **Managed LLM / GenAI** | **Amazon Bedrock** (Claude, Amazon Nova) | **Vertex AI** (Gemini 2.5 Flash/Pro, Claude у Model Garden) | **Defer / Compare in Part 4** | Vertex AI надає єдиний API для моделей Gemini та партнерських моделей (зокрема Anthropic Claude). Для парсингу фото рукописних адженд додатково протестовано **Cloud Vision API / Document AI**. |
| **Secrets & Config** | **SSM Parameter Store / Secrets Manager** | **Secret Manager** | **Replace → Secret Manager** | Нативна інтеграція з Cloud Run: секрет (наприклад, `DATABASE_URL` або `DB_PASSWORD`) монтується безпосередньо як змінна середовища контейнера при старті. 6 активних версій секретів та 10 000 звернень на місяць — **$0**. |
| **Centralized Logging** | **Amazon CloudWatch Logs** | **Cloud Logging** | **Replace → Cloud Logging** | Усі потоки `stdout`/`stderr` із Cloud Run та логи Cloud SQL автоматично потрапляють у Cloud Logging без налаштування агентів. Перші **50 GiB/міс — безкоштовні**. |
| **Identity & Access (IAM)** | **IAM Roles & Execution Policies** | **Service Accounts + IAM Roles** | **Replace → Dedicated Service Account** | Створюється окремий сервісний акаунт `spry-backend-sa` з мінімальними ролями (`roles/cloudsql.client`, `roles/secretmanager.secretAccessor`, `roles/logging.logWriter`). Жодних довгоживучих JSON-ключів у репозиторії. |
| **Infrastructure as Code** | **Terraform (`hashicorp/aws`)** у папці `infra/` | **Terraform (`hashicorp/google`)** у папці `gcp/` | **Replace → Окремий модуль `gcp/`** | Окремий кореневий модуль `gcp/` із власним Terraform state дозволяє незалежно розгортати та знищувати інфраструктуру в обох хмарах паралельно. |

---

## 3. Ключові архітектурні рішення (Обов'язкові питання ADR)

### 3.1. Вибір бази даних: Cloud SQL vs Firestore vs Cross-Cloud DB

База даних — це єдиний компонент нашої архітектури, який має **стан (state)** і найбільше впливає як на трудомісткість міграції, так і на щомісячний рахунок. Ми проаналізували чотири варіанти:

1. **Варіант А (Обраний для реалізації у Фазі 1): Cloud SQL for PostgreSQL (`db-f1-micro`, 10 GB SSD) у режимі роботи або за розкладом.**
   - **Переваги:** Повна сумісність на рівні драйвера `psycopg2`/`asyncpg`, моделей SQLAlchemy та міграцій `alembic upgrade head`. Перенесення схеми та даних займає хвилини (`pg_dump` → `psql`), жодного рядка Python-коду в `back/app/` переписувати не потрібно.
   - **Компроміс за вартістю:** На відміну від Aurora Serverless v2 з auto-pause до 0 ACU, інстанс `db-f1-micro` не вміє автоматично засинати між запитами. Якщо він працює 24/7 (730 год/міс), обчислення коштують **$7.67/міс** ($0.0105/год) + **$1.70/міс** за 10 GB SSD = **$9.37/міс**.
   - **Оптимізація (FinOps):** Зупинка інстансу на ніч та вихідні (`gcloud sql instances patch ... --activation-policy=NEVER`) знижує витрати на compute пропорційно годинам простою (у повністю зупиненому стані платимо лише **$1.70/міс** за 10 GB диска).

2. **Варіант Б: Перехід на Cloud Firestore (NoSQL).**
   - **Переваги:** Справжній scale-to-zero з безкоштовною квотою **50 000 читань, 20 000 записів та 1 GiB зберігання щодня**. Для навчального проєкту або MVP з невеликим трафіком вартість становить рівно **$0.00/міс**.
   - **Чому не обрано для миттєвого переносу:** Наш бекенд побудований навколо реляційної схеми PostgreSQL (таблиці `users`, `meetings`, `participants`, зовнішні ключі, транзакції SQLAlchemy та Alembic). Перехід на Firestore вимагав би повної заміни шару репозиторіїв (`Session` → `google-cloud-firestore`), денормалізації зв'язків «багато-до-багатьох» та відмови від SQL-міграцій. Тому Firestore зафіксовано як стратегічну альтернативу для greenfield serverless-сервісів, де критичний $0 idle bill.

3. **Варіант В: Cross-Cloud DB (Cloud Run у GCP звертається до Aurora у AWS).**
   - **Чому відхилено:** Хоча технічно можливо відкрити доступ до БД між хмарами, це антипатерн для транзакційного вебзастосунку:
     - **Мережева затримка (Latency):** Кожен SQL-запит (а один HTTP-запит часто виконує 3–5 звернень до БД плюс TCP/TLS handshake) долатиме міжхмарний маршрут між датацентрами Google (`us-central1`, Iowa) та AWS (`us-east-1`, Virginia або `eu-north-1`, Stockholm), додаючи **20–80 мс на кожен round-trip**.
     - **Подвійна тарифікація трафіку (Data Egress):** AWS та GCP тарифікують вихідний трафік у публічний Інтернет ($0.09–$0.12/GB).
     - **Безпека та надійність:** Вимагає або виставлення БД у публічний інтернет зі складними IP-фільтрами (оскільки Cloud Run без Cloud NAT має динамічні вихідні IP), або платного VPN / Cloud Interconnect між VPC обох провайдерів, що нівелює будь-яку економію.

### 3.2. Відправка транзакційних листів (Email Service)

На відміну від AWS, де є вбудований та дешевий **Amazon Simple Email Service (SES)** ($0.10 за 1000 листів), **Google Cloud Platform не має власного нативного сервісу для відправки транзакційних чи маркетингових email-ів**.

**Наше архітектурне рішення:**
- Використовувати спеціалізований зовнішній Email API провайдер — **SendGrid** (або **Mailgun / Resend**), який офіційно інтегрований у GCP Marketplace, або залишити виклик **AWS SES** через HTTPS API як мультиклауд-компонент.
- **Керування секретами:** API-ключ провайдера (`SENDGRID_API_KEY` або кредами SES) **ніколи не зберігається у git чи `Dockerfile`**. Він створюється як секрет у **GCP Secret Manager** (`google_secret_manager_secret`), а сервісний акаунт Cloud Run отримує роль `roles/secretmanager.secretAccessor` і зчитує ключ зі змінної середовища під час запуску контейнера.

### 3.3. Межі міграції у Фазі 1 (Scope & Non-Goals)

Щоб мінімізувати ризики при переході на нову хмару, ми застосовуємо ітеративний підхід (**Strangler Fig / Core-First Migration**):

- **Що переноситься в GCP у межах цієї лабораторної роботи (Core Vertical Slice):**
  1. **Інфраструктура як код (`gcp/`):** Terraform-конфігурація провайдера `google`, автоматичне увімкнення API, IAM Service Account, Secret Manager, Artifact Registry.
  2. **База даних:** Cloud SQL for PostgreSQL (`db-f1-micro`) зі схемою даних нашого застосунку (`alembic upgrade head`).
  3. **Бекенд API (`back/Dockerfile.gcp`):** Контейнеризований FastAPI-сервіс у **Cloud Run** (`min_instance_count = 0`, `max_instance_count = 2`), підключений до Cloud SQL та Secret Manager.
  4. **Фронтенд (`gcp/firebase.json`):** Статичний бандл React-застосунку на **Firebase Hosting** з проксуванням `/api/**` на Cloud Run (єдиний домен без CORS).

- **Що свідомо залишається на AWS / винесено у Фазу 2 (Stretch Goals):**
  1. **Автентифікація (Cognito → Identity Platform):** Перенесення пулу користувачів та переналаштування Google OAuth Consent Screen на новий redirect URI не блокує перевірку працездатності Core API та БД.
  2. **Тижневий пайплайн звітів (EventBridge → S3 → Lambda → SES):** Цей асинхронний контур був реалізований у попередніх лабораторних і може працювати автономно або бути перенесеним пізніше на зв'язку `Cloud Scheduler → Cloud Run → Cloud Storage → SendGrid`.
  3. **LLM-парсер адженди (Bedrock Claude → Vertex AI Gemini / Vision API):** Прямий порівняльний аналіз LLM-парсера з **Google Cloud Vision API / Document AI** та **BigQuery / Looker Studio** винесено в аналітично-демонстраційну частину (**Part 4**).

---

## 4. Наслідки рішення (Consequences)

### Позитивні:
- **Нульові зміни в бізнес-логіці бекенду:** Завдяки зв'язці `Cloud Run + Cloud SQL for PostgreSQL` код FastAPI, SQLAlchemy та Alembic працює в обох хмарах без модифікацій.
- **Простіший контейнерний стек:** У GCP не потрібен специфічний прошарок AWS Lambda Web Adapter — Cloud Run нативно обслуговує стандартний HTTP-контейнер.
- **Відсутність CORS-проблем:** Firebase Hosting rewrites дозволяють роздавати SPA та проксувати `/api/**` у Cloud Run на одному домені `*.web.app` безкоштовно.
- **Прозорий FinOps-контроль:** Усі ресурси описані в `gcp/*.tf` і можуть бути повністю видалені однією командою `terraform destroy`.

### Ризики та обмеження:
- **Фіксована вартість Cloud SQL у режимі 24/7:** На відміну від Aurora Serverless v2 (яка засинає до $0 compute при нульовому трафіку), `db-f1-micro` коштує $7.67/міс за обчислення, якщо її не зупиняти примусово (`--activation-policy=NEVER`).
- **Холодні старти Cloud Run:** При `min_instance_count = 0` перший запит після простою займає ~1.5–3 секунди на підняття контейнера та ініціалізацію пулу з'єднань SQLAlchemy.
