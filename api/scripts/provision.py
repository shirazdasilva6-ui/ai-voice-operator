"""Re-run provisioning for one customer, e.g. after setting phone_number by hand for a UAE client.

    python -m scripts.provision <customer_id>
"""
import sys

from app.db import pool
from app.provisioning import provision_customer

if __name__ == "__main__":
    pool.open(wait=True)
    provision_customer(sys.argv[1])
    pool.close()
