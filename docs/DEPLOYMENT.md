# Configuration and deployment

## Local development

Console codes + demo AI are the defaults. Use port 5001. No email is sent and no Gemini calls occur unless configured. Local secrets, database and uploads live under `backend/instance/`, excluded from version control.

## Real email

Set AUTH_DELIVERY=smtp and configure SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USERNAME and SMTP_PASSWORD in .env. Use your provider's SMTP/app credentials, not a password pasted into chat. Port 587 uses STARTTLS; 465 uses implicit TLS. Configure your sender/domain with your provider before testing. Request a code with an email address you control and confirm it actually arrives before inviting users.

## Deployment outside localhost

1. Set APP_ENV=production, AUTH_DELIVERY=smtp, and a unique SECRET_KEY of at least 32 random characters. Generate locally using `python -c "import secrets; print(secrets.token_hex(32))"` and store privately.
2. Configure SMTP and optional Gemini settings. Run `python manage.py init` once before starting workers.
3. Use HTTPS through your host/reverse proxy. Start with `gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5001 app:app`.
4. Route the frontend and /api through the same public origin when possible. If using separate origins, explicitly configure ALLOWED_ORIGINS and browser cookie behavior; Lax cookies do not support arbitrary cross-site embedding.
5. Persist the instance directory and uploads on durable storage. SQLite is suitable for a small single-host hackathon deployment. Do not use multiple independent containers with separate local databases for the same service.
6. Run `python manage.py cleanup` regularly (for example hourly using your hosting scheduler) to physically remove expired recordings and session data. API access checks already reject expired records.
7. Back up database and uploads together. Test recovery before relying on them.
8. Test actual email delivery, image upload, two browsers/users, and Gemini with your own project. Validate logs do not contain sensitive data. Console OTP delivery is blocked by the production configuration guard.

No server, account, API project or public URL was provisioned for you. External credentials and hosting remain user configuration. The backend has not undergone an independent security audit. Multi-account collusion in reputation, moderation and operational incident recovery need further work before broad campus deployment.

## Classroom references and official guidance

Room-reference files are manually curated and never auto-downloaded from user URLs. Check permission and attribution before copying Rutgers material. Suggested rooms require confirmation. No institutional partnership or staff-verification workflow is implied.

Official sources checked while preparing the package:
- https://dcs.rutgers.edu/learning-spaces/
- https://dcs.rutgers.edu/learning-spaces/general-purpose-classrooms/
- https://ipo.rutgers.edu/publicsafety/lost-found-nb
- https://sca.rutgers.edu/services/lost-and-found
- https://ipo.rutgers.edu/publicsafety/iam/lost-found-ruid

Use the current official guidance for sensitive items and staffed hand-in procedures; the application records user-reported custody separately from confirmed receipt.
