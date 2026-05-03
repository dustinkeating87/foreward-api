# Good Lie API

FastAPI backend for the Good Lie tee time alert system.

## Stack

- **FastAPI** — REST API
- **Supabase** — Postgres database + Auth
- **Stripe** — $10/month subscription billing
- **uvicorn** — ASGI server

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Project URL from Supabase dashboard |
| `SUPABASE_KEY` | `anon` public key |
| `SUPABASE_SERVICE_KEY` | `service_role` secret key (bypasses RLS) |
| `STRIPE_SECRET_KEY` | Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | From `stripe listen` or Stripe dashboard webhook |
| `STRIPE_PRICE_ID` | Price ID of the $10/month recurring price |
| `BASE_URL` | API base URL |
| `SUCCESS_URL` | Redirect after successful checkout |
| `CANCEL_URL` | Redirect after cancelled checkout |

### 3. Set up Supabase schema

Run the following SQL in your Supabase SQL editor:

```sql
-- User profiles (extends auth.users)
CREATE TABLE public.user_profiles (
    id          UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email       TEXT,
    is_active   BOOLEAN DEFAULT FALSE,
    is_beta     BOOLEAN DEFAULT FALSE,
    stripe_customer_id     TEXT,
    stripe_subscription_id TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own profile"
    ON public.user_profiles FOR SELECT
    USING (auth.uid() = id);

-- Alert profiles
CREATE TABLE public.alert_profiles (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id      UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    courses      TEXT[] DEFAULT '{}',
    date_from    DATE NOT NULL,
    date_to      DATE NOT NULL,
    time_from    TEXT NOT NULL,
    time_to      TEXT NOT NULL,
    players      INTEGER NOT NULL,
    holes        INTEGER NOT NULL,
    notify_email TEXT,
    notify_phone TEXT,
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.alert_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own alerts"
    ON public.alert_profiles FOR ALL
    USING (auth.uid() = user_id);

-- Auto-create user_profiles row on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email)
    VALUES (NEW.id, NEW.email);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

### 4. Create Stripe price

In the Stripe dashboard (or CLI), create a recurring price:

```bash
stripe prices create \
  --unit-amount 1000 \
  --currency usd \
  --recurring[interval]=month \
  --product-data[name]="Good Lie"
```

Copy the resulting `price_...` ID into `STRIPE_PRICE_ID`.

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 6. Set up Stripe webhooks (local dev)

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Copy the `whsec_...` secret into `STRIPE_WEBHOOK_SECRET`.

For production, add the webhook endpoint in the Stripe dashboard pointing to `https://your-domain/webhooks/stripe` and handle:
- `checkout.session.completed`
- `customer.subscription.deleted`

---

## API Reference

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create account |
| POST | `/auth/login` | — | Login, returns JWT |
| GET | `/auth/me` | Bearer | Current user + profile |

### Alerts

All alert endpoints require a valid JWT **and** an active subscription (or `is_beta = true`).

| Method | Path | Description |
|---|---|---|
| POST | `/alerts` | Create alert profile |
| GET | `/alerts` | List your alert profiles |
| PUT | `/alerts/{id}` | Update alert profile |
| DELETE | `/alerts/{id}` | Delete alert profile |

### Billing

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/create-checkout-session` | Bearer | Creates Stripe checkout URL |
| POST | `/webhooks/stripe` | Stripe sig | Handles subscription events |

### Export

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/export-alerts` | Bearer | All active alerts in `alerts.json` format |

---

## Beta Users

Set `is_beta = true` on a `user_profiles` row to grant permanent access without a subscription:

```sql
UPDATE public.user_profiles SET is_beta = TRUE WHERE email = 'user@example.com';
```
