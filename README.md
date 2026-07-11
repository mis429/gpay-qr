# gpay_qr — Collect UPI payments by QR code (with confirmation)

A small Python CLI that generates a UPI payment QR code, then tells you when the
money actually arrives.

## How it works (read this first)

- **To receive money**, all a payer needs is a UPI QR. That part is free.
- **To have your program CONFIRM the payment**, you need a payment gateway with an
  API. This project uses **Razorpay**. Money you collect settles into the **bank
  account** you link during Razorpay KYC — not directly into the GPay app balance.
- There is **no legitimate way** to programmatically confirm payments landing
  directly in a personal GPay account. The gateway is the supported path.

Two modes:

| Mode | Confirms payment? | Needs account? | Command |
|------|-------------------|----------------|---------|
| `gateway` (default) | ✅ yes | Razorpay (free signup + KYC for live) | `python pay.py 500` |
| `offline` | ❌ no (check GPay app) | none | `python pay.py 500 --offline` |

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create your config:
   ```
   copy .env.example .env      (Windows)
   ```
   Then edit `.env`.

3. **For gateway mode:** sign up at https://razorpay.com → Dashboard →
   Settings → API Keys → generate keys. Put them in `.env`.
   - Start with **test** keys (`rzp_test_...`) to build/wire everything.
   - Complete **KYC** and switch to **live** keys (`rzp_live_...`) to accept real money.
   - The **QR Codes** feature must be enabled on your account (usually on by default;
     if creation fails, ask Razorpay support to enable "QR Codes").

4. **For offline mode:** just set `MY_UPI_ID` in `.env` (e.g. `yourname@okhdfcbank`).

## Usage

```
python pay.py 500                    # collect ₹500, wait for confirmation
python pay.py 500 --note "Order #42" # with a note
python pay.py 250 --timeout 600      # wait up to 10 minutes
python pay.py 100 --offline          # quick static QR, no confirmation
```

The QR image is saved under `qrcodes/` and opened automatically.

## Notes & next steps

- **Test mode** can't be paid with a real UPI app; use it only to verify your code
  runs and keys work. Real end-to-end testing happens with live keys after KYC.
- Polling (what this script does) is perfect for a CLI. For a website/always-on
  service, use Razorpay **webhooks** instead — ask and I can add that.
- Never commit `.env` (already in `.gitignore`).
