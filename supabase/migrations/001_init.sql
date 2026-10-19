create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  phone text unique not null,
  name text,
  email text,
  company text,
  budget_usd int,
  is_decision_maker boolean,
  need text,
  timeline_days int,
  score int,
  status text not null default 'new', -- new | needs_info | qualified | disqualified | booked
  hubspot_id text,
  booking_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists calls (
  id uuid primary key default gen_random_uuid(),
  external_id text unique not null,
  channel text not null check (channel in ('voice', 'whatsapp')),
  lead_id uuid references leads(id),
  duration_s numeric,
  cost_usd numeric,
  outcome text,
  summary text,
  transcript text,
  simulated boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists tool_events (
  id bigserial primary key,
  call_external_id text,
  tool text not null,
  latency_ms int not null,
  ok boolean not null,
  created_at timestamptz not null default now()
);

create table if not exists messages (
  id bigserial primary key,
  phone text not null,
  role text not null,
  content jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists messages_phone_idx on messages (phone, created_at);

create table if not exists customers (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  stripe_customer_id text unique,
  stripe_subscription_id text,
  status text,
  created_at timestamptz not null default now()
);
