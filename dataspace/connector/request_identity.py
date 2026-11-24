"""Allowlisted request metadata for demo logs; never capture credentials or all headers."""
from contextvars import ContextVar

requester = ContextVar('call_requester', default={})


def http_identity(request):
    if request is None:
        return {}
    headers = request.headers
    fields = {
        'session_id': headers.get('mcp-session-id'),
        'client_id': headers.get('x-demo-client-id'),
        'user_agent': headers.get('user-agent'),
        'protocol_version': headers.get('mcp-protocol-version'),
        'remote_address': request.client.host if request.client else None,
        'forwarded_for': headers.get('x-forwarded-for'),
    }
    return {key: str(value)[:512] for key, value in fields.items() if value is not None}


async def capture_requester(ctx, call_next):
    info = http_identity(ctx.request)
    if ctx.request_id is not None:
        info['request_id'] = str(ctx.request_id)[:512]
    info['protocol_version'] = str(ctx.protocol_version)[:512]
    params = ctx.session.client_params
    client = getattr(params, 'client_info', None) if params else None
    if client:
        for field in ('name', 'version', 'title'):
            value = getattr(client, field, None)
            if value:
                info['client_' + field] = str(value)[:512]
    token = requester.set(info)
    try:
        return await call_next(ctx)
    finally:
        requester.reset(token)
