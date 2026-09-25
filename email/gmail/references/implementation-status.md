# Implementation status

This Skill uses Gmail IMAP/SMTP with a local Google app password. Create the app password after enabling Google 2-Step Verification, then fill the ignored `config/imap-smtp.local.json` from `config/imap-smtp.example.json`.

The workflow supports message search, body reading, attachment preview/download, audit logs, storage checks, and confirmation-gated sending. It never stores OAuth clients, access tokens, or refresh tokens.
