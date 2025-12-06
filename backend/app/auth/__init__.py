"""
Supabase authentication module for sales-agent.

This module provides Supabase-based authentication including:
- Email/password authentication
- Magic link authentication
- JWT token validation
- Role-based access control
- Password reset flows
"""

from .supabase_auth import SupabaseAuthClient, get_supabase_client

__all__ = ["SupabaseAuthClient", "get_supabase_client"]
