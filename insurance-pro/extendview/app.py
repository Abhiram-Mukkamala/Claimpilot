"""
ClaimPilot AI — ExtendView Unified Entrypoint Router (app.py)
=============================================================
Allows running either Customer Extended View or Agent Extended View via:
  1. Separate Streamlit entrypoints (recommended for dual-port / dual-service hosting):
       streamlit run customer_app.py --server.port 8501
       streamlit run agent_app.py --server.port 8502
  2. Single entrypoint dispatched by `EXTENDVIEW_ROLE` env var or `?role=customer|agent`:
       streamlit run app.py
"""

import os
import streamlit as st

from customer_app import run_customer_extendview
from agent_app import run_agent_extendview


def main():
    st.set_page_config(
        page_title="ClaimPilot AI | Extended 3D & DSINE View",
        layout="wide",
        page_icon="🛡️",
    )

    qp = st.query_params
    role = (qp.get("role") or os.environ.get("EXTENDVIEW_ROLE") or "agent").lower()

    if role == "customer":
        run_customer_extendview(set_page_cfg=False)
    else:
        run_agent_extendview(set_page_cfg=False)


if __name__ == "__main__":
    main()
