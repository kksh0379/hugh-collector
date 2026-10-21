"""Entry point for future Render daily-mail cron job.

Until digest content is approved, automated sending stays disabled.
This avoids emailing unfinished or placeholder content.
"""
import os
from datetime import datetime, timezone


def main():
    if os.getenv("MAIL_DAILY_ENABLED", "false").lower() != "true":
        print("Daily mail disabled; no message sent.")
        return
    # The editorial digest renderer will be connected when content is approved.
    # Never send repeated connection-test messages as a daily digest.
    raise RuntimeError("Daily mail content is not configured; automatic sending blocked.")


if __name__ == "__main__":
    main()
