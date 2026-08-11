"""Aggregate router for v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    buvette,
    events,
    expenses,
    invitations,
    invoices,
    poles,
    scan,
    stock,
    users,
)


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(stock.router)
api_router.include_router(expenses.router)
api_router.include_router(invoices.router)
api_router.include_router(poles.router)
api_router.include_router(events.router)
api_router.include_router(admin.router)
api_router.include_router(buvette.router)
api_router.include_router(scan.router)
