alter table customers
  add column if not exists country text,
  add column if not exists business_name text,
  add column if not exists provisioning_status text not null default 'pending', -- pending | provisioning | needs_manual_number | failed | live
  add column if not exists provisioning_error text,
  add column if not exists vapi_assistant_id text,
  add column if not exists vapi_phone_number_id text,
  add column if not exists phone_number text,
  add column if not exists twilio_number_sid text,
  -- lets a run that died mid-way (server restart) be reclaimed instead of staying 'provisioning' forever
  add column if not exists provisioning_started_at timestamptz;
