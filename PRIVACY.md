# Privacy Policy — Bilancio

*Last updated: 2026-04-12*

---

## What is Bilancio?

Bilancio is a personal finance tracker that helps you understand where your money goes. You upload
your own bank statement files; Bilancio stores and categorizes the transactions.

This instance is operated by **[Operator name — fill in before inviting users]** (the "operator").

---

## What data is collected?

Bilancio stores only data that you explicitly upload or enter:

- **Bank transactions**: date, amount, description, and category — extracted from the statement
  files you upload.
- **Categorization rules and categories** you create.
- **Your email address and display name**, provided when the operator creates your account.
- **Usage logs**: timestamps and anonymized request metadata for operational purposes (no
  transaction content is logged).
- **Audit log**: a record of every change made to your data, including the action and timestamp.

Bilancio does **not**:
- Connect directly to your bank (no PSD2/Open Banking integration).
- Collect analytics, telemetry, or advertising data.
- Share your data with third parties.

---

## Where is data stored?

All data is stored in **Microsoft Azure, Italy North region (Milan, Italy)**, within the European
Union. Specifically:

| Component | Service | Location |
|---|---|---|
| Transaction data | Azure Database for PostgreSQL | Italy North |
| Uploaded statement files | Azure Blob Storage | Italy North |
| Application logs | Azure Log Analytics | Italy North |

Data is encrypted at rest (Azure default) and in transit (TLS 1.2+).

---

## Lawful basis (GDPR)

The lawful basis for processing your personal data is **consent**. By accepting an API token from
the operator and uploading your bank statements, you consent to Bilancio storing and processing
that data to provide the finance tracking service.

You may withdraw consent at any time by requesting account deletion (see below).

---

## Your rights

Under GDPR, you have the right to:

- **Access your data**: request a full export of everything Bilancio holds about you.
- **Portability**: receive your data in a structured, machine-readable format (JSON).
- **Deletion ("right to be forgotten")**: request that your data be deleted.
- **Correction**: ask the operator to correct inaccurate personal data.
- **Restriction**: ask the operator to restrict processing while a dispute is resolved.

### How to exercise your rights

**Via the API** (requires your API token):

```
# Export all your data as JSON
GET /me/export
Authorization: Bearer <your-token>

# Delete your account (soft-delete; hard-delete after 30 days)
DELETE /me
Authorization: Bearer <your-token>
```

**By contacting the operator**: [operator email — fill in before inviting users]

The operator will respond to requests within **30 days**.

---

## Data retention

- **Active accounts**: data is retained for as long as your account is active.
- **Deleted accounts**: data is anonymized immediately on deletion request; hard-deleted after
  30 days. The audit log entry for the deletion request is retained for legal compliance.
- **Backups**: automated backups are retained for 7 days (point-in-time restore). Weekly logical
  backups are retained for 90 days.

---

## Data breach notification

In the event of a data breach that poses a risk to your rights and freedoms, the operator will:

1. Notify the relevant supervisory authority within **72 hours** of becoming aware (as required
   by GDPR Article 33).
2. Notify affected users without undue delay if the breach is likely to result in high risk to
   their rights.

Contact for security issues: [operator email — fill in]

---

## Contact

For any privacy-related questions or requests:

**Operator**: [Name — fill in]  
**Email**: [Email — fill in]  
**Country**: Italy

You also have the right to lodge a complaint with the Italian data protection authority:
**Garante per la protezione dei dati personali** — [www.garanteprivacy.it](https://www.garanteprivacy.it)

---

*This policy applies to this specific instance of Bilancio. The Bilancio software is open-source;
other operators running their own instances are responsible for their own privacy policies.*
