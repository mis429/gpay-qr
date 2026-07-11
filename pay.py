"""
gpay_qr - Collect UPI payments with a QR code and confirm them from the CLI.

Two modes:
  1. gateway (default) : Creates a REAL, confirmable QR via Razorpay. Any UPI app
                         (GPay / PhonePe / Paytm) can scan and pay. The script then
                         polls Razorpay until the payment is captured and prints a
                         confirmation. Money settles into your Razorpay-linked bank
                         account.
  2. offline           : Generates a plain static UPI QR to your own UPI ID. Free,
                         no account needed, but the script CANNOT confirm payment
                         (you check your GPay app). Handy for a quick test.

Usage:
    python pay.py 500                       # collect Rs 500 (gateway mode + confirmation)
    python pay.py 500 --note "Order #42"    # add a note/description
    python pay.py 500 --offline             # static QR to MY_UPI_ID, no confirmation
    python pay.py 500 --timeout 600         # wait up to 600s for payment (default 300)

Setup: see README.md. You must copy .env.example to .env and fill it in.
"""

import argparse
import os
import sys
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

QR_DIR = Path(__file__).parent / "qrcodes"


def rupees_to_paise(amount_rupees: float) -> int:
    """UPI/Razorpay work in paise (integer). Rs 1 = 100 paise."""
    return int(round(amount_rupees * 100))


def open_file(path: Path) -> None:
    """Best-effort open of the saved QR image in the OS default viewer."""
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Offline mode: static UPI QR, no confirmation
# --------------------------------------------------------------------------- #
def run_offline(amount_rupees: float, note: str) -> int:
    import qrcode

    upi_id = os.getenv("MY_UPI_ID", "").strip()
    name = os.getenv("MERCHANT_NAME", "Merchant").strip()
    if not upi_id:
        print("ERROR: --offline needs MY_UPI_ID set in your .env file "
              "(e.g. yourname@okhdfcbank).")
        return 1

    # Standard UPI deep-link. Any UPI app can parse this.
    uri = (
        f"upi://pay?pa={upi_id}&pn={name}"
        f"&am={amount_rupees:.2f}&cu=INR"
    )
    if note:
        uri += f"&tn={note.replace(' ', '%20')}"

    QR_DIR.mkdir(exist_ok=True)
    out = QR_DIR / f"offline_{int(amount_rupees)}rs.png"
    qrcode.make(uri).save(out)

    print(f"Static UPI QR saved to: {out}")
    print(f"Pay-to: {upi_id}  |  Amount: Rs {amount_rupees:.2f}")
    print("NOTE: Offline mode cannot confirm payment. Check your GPay app.")
    open_file(out)
    return 0


# --------------------------------------------------------------------------- #
# Gateway mode: Razorpay QR with confirmation via polling
# --------------------------------------------------------------------------- #
def run_gateway(amount_rupees: float, note: str, timeout: int) -> int:
    import razorpay
    import requests

    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    name = os.getenv("MERCHANT_NAME", "Merchant").strip()

    if not key_id or not key_secret or key_id.startswith("rzp_test_xxx"):
        print("ERROR: Razorpay keys missing. Copy .env.example to .env and set")
        print("       RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
        print("       (Or run with --offline to generate a static QR without an account.)")
        return 1

    client = razorpay.Client(auth=(key_id, key_secret))
    amount_paise = rupees_to_paise(amount_rupees)

    print(f"Creating QR for Rs {amount_rupees:.2f} ...")
    try:
        qr = client.qrcode.create({
            "type": "upi_qr",
            "name": name,
            "usage": "single_use",
            "fixed_amount": True,
            "payment_amount": amount_paise,
            "description": note or f"Payment to {name}",
            "close_by": int(time.time()) + max(timeout, 300) + 60,
        })
    except Exception as e:
        print(f"ERROR creating QR: {e}")
        print("Common cause: the QR Codes feature isn't enabled on your account. "
              "Ask Razorpay support to enable it, or use --offline for now.")
        return 1

    qr_id = qr["id"]
    image_url = qr.get("image_url")

    QR_DIR.mkdir(exist_ok=True)
    out = QR_DIR / f"{qr_id}.png"
    try:
        img = requests.get(image_url, timeout=30)
        img.raise_for_status()
        out.write_bytes(img.content)
        print(f"QR saved to: {out}")
        open_file(out)
    except Exception as e:
        print(f"(Could not download image, open this URL instead: {image_url})  [{e}]")

    print(f"\nScan with any UPI app to pay Rs {amount_rupees:.2f}.")
    print(f"Waiting for payment (up to {timeout}s)... press Ctrl+C to stop.\n")

    deadline = time.time() + timeout
    poll_every = 4
    try:
        while time.time() < deadline:
            payments = client.qrcode.fetch_all_payments(qr_id)
            for p in payments.get("items", []):
                if p.get("status") == "captured":
                    paid = p["amount"] / 100
                    print("=" * 48)
                    print(f"PAYMENT RECEIVED: Rs {paid:.2f}")
                    print(f"  Payment ID : {p['id']}")
                    print(f"  Method     : {p.get('method', 'upi')}")
                    vpa = p.get("vpa") or p.get("upi", {}).get("vpa")
                    if vpa:
                        print(f"  Paid by    : {vpa}")
                    print("=" * 48)
                    return 0
            remaining = int(deadline - time.time())
            print(f"  ...waiting ({remaining}s left)", end="\r", flush=True)
            time.sleep(poll_every)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130

    print("\nTimed out. No payment detected yet.")
    print(f"You can check status later in the Razorpay dashboard (QR id: {qr_id}).")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect UPI payment via QR code.")
    parser.add_argument("amount", type=float, help="Amount in rupees, e.g. 500")
    parser.add_argument("--note", default="", help="Note/description for the payment")
    parser.add_argument("--offline", action="store_true",
                        help="Static QR to MY_UPI_ID (no payment confirmation)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Seconds to wait for payment in gateway mode (default 300)")
    args = parser.parse_args()

    if args.amount <= 0:
        print("Amount must be greater than 0.")
        return 1

    load_dotenv(Path(__file__).parent / ".env")

    if args.offline:
        return run_offline(args.amount, args.note)
    return run_gateway(args.amount, args.note, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
