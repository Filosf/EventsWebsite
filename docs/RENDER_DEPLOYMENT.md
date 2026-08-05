# Развертывание на Render и Cloudflare R2

Эта схема создает один веб-сервис Render Starter, платную Render PostgreSQL,
бесплатный Render Key Value (Redis) и бакет Cloudflare R2. Инфраструктура описана
в `render.yaml`; каждый push в `main` сначала проходит GitHub Actions, после чего
Render автоматически выполняет миграции и выпускает новую версию.

## 1. Подготовьте домен

Собственный домен приложения необязателен: Render автоматически выдаст сервису
адрес `*.onrender.com` и TLS-сертификат. Если позже понадобится красивый адрес,
зарезервируйте имя вроде `events.example.com`.

Для production-домена файлов R2 нужна DNS-зона в Cloudflare. Зарезервируйте имя:

- `media.example.com` для баннеров и других загруженных файлов.

Вместо `example.com` далее используйте свой домен. Render и Cloudflare выпускают
и продлевают TLS-сертификаты автоматически.

## 2. Создайте Cloudflare R2

1. В Cloudflare откройте **R2 Object Storage** и активируйте сервис. Cloudflare
   может запросить платежный профиль, даже если использование укладывается в
   бесплатный лимит.
2. Нажмите **Create bucket**, задайте имя `events-website-media`, тип хранения
   **Standard** и подходящее европейское размещение.
3. Откройте бакет, затем **Settings > Custom Domains > Connect Domain** и
   подключите `media.example.com`.
4. В разделе **R2 > Manage R2 API Tokens** создайте токен с правом
   **Object Read & Write**, ограниченным только бакетом `events-website-media`.
5. Сохраните показанные один раз значения **Access Key ID**, **Secret Access
   Key** и S3 endpoint вида `https://<account-id>.r2.cloudflarestorage.com`.
6. Не используйте публичный адрес `r2.dev` в рабочей среде: приложение будет
   публиковать файлы через `media.example.com`.

## 3. Подключите GitHub к Render

1. В Render откройте **Account Settings > Git Providers** и подключите GitHub.
2. Разрешите Render доступ к репозиторию `Filosf/EventsWebsite`. Доступа только к
   этому репозиторию достаточно.
3. В Dashboard нажмите **New > Blueprint**, выберите репозиторий и ветку `main`.
4. Render обнаружит корневой `render.yaml`. Оставьте **Auto Sync** включенным.
5. Проверьте список ресурсов перед подтверждением: `events-website` на Starter,
   `events-db` на `Basic-256mb` и `events-cache` на Free.

Blueprint попросит значения переменных с `sync: false`. Заполните их так:

| Переменная | Значение |
| --- | --- |
| `R2_ENDPOINT_URL` | точный S3 endpoint из Cloudflare |
| `R2_ACCESS_KEY_ID` | Access Key ID токена R2 |
| `R2_SECRET_ACCESS_KEY` | Secret Access Key токена R2 |
| `R2_BUCKET_NAME` | `events-website-media` |
| `R2_CUSTOM_DOMAIN` | `media.example.com` без `https://` |

`SECRET_KEY`, `DATABASE_URL` и `REDIS_URL` создаются или связываются самим
Blueprint. Не добавляйте эти значения в GitHub и не записывайте их в `.env` в
репозитории.

## 4. Подключите домен приложения

Этот раздел необязателен. Стандартный адрес `*.onrender.com` уже работает через
HTTPS. Для подключения собственного домена:

1. После создания ресурсов откройте `events-website` в Render.
2. В **Settings > Custom Domains** добавьте `events.example.com`.
3. В Cloudflare DNS создайте запись, которую покажет Render. Удалите конфликтующие
   записи `A`, `AAAA` или `CNAME` для этого поддомена.
4. Дождитесь статуса **Verified** и выпуска сертификата. Проверяйте сначала
   `https://events.example.com/healthz/`, затем страницу `/admin/`.

На время настройки доступен и стандартный адрес `*.onrender.com` с HTTPS.

## 5. Создайте первого администратора

1. В Render откройте `events-website` и добавьте временные secret-переменные
   `ADMIN_EMAIL` и `ADMIN_PASSWORD` с надежным уникальным паролем.
2. После перезапуска откройте **Shell** и выполните:

   ```bash
   python manage.py bootstrap_admin
   python manage.py release_preflight
   ```

3. Сразу удалите `ADMIN_EMAIL` и `ADMIN_PASSWORD` из Environment. Учетная запись
   останется в PostgreSQL; временные секреты приложению больше не нужны.
4. Войдите на `/admin/` и создайте рабочее мероприятие. Команда `seed_demo` в
   production намеренно заблокирована.

## 6. Автоматические релизы через Git

Обычный выпуск выглядит так:

```powershell
git add .
git commit -m "Describe the change"
git push origin main
```

GitHub Actions запускает линтер, системные проверки Django, проверку миграций и
тесты. Render использует `autoDeployTrigger: checksPass`, поэтому начинает сборку
только после успешного CI. Перед переключением версии выполняется `migrate`, а
`/healthz/` используется как health check.

Изменения `render.yaml` автоматически синхронизируются Blueprint. Изменения схемы
моделей должны всегда приходить вместе с миграцией. Пароли, токены, содержимое
PostgreSQL и файлы R2 никогда не коммитятся.

## 7. Эксплуатационный минимум

- Перед значительными миграциями создавайте manual logical export PostgreSQL в
  Render. Платная база также имеет управляемое восстановление, но экспорт дает
  независимую контрольную точку.
- Проверяйте расходы и лимиты в Billing двух сервисов: Render и Cloudflare.
- При ошибке откройте **Deploys** в Render и выполните rollback на последний
  рабочий deploy; данные PostgreSQL и файлы R2 при этом не откатываются.
- Не удаляйте базу или бакет через Blueprint без отдельной резервной копии.
