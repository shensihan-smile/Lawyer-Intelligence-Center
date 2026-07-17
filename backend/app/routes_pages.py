"""前端页面路由 — 使用 Jinja2 模板渲染"""
import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

router = APIRouter()

# 模板目录
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


def _render(page_name: str, request: Request) -> HTMLResponse:
    """渲染模板"""
    template = jinja_env.get_template("index.html")
    html = template.render(request=request, page=page_name)
    return HTMLResponse(content=html)


@router.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    return _render("dashboard", request)


@router.get("/clients", response_class=HTMLResponse)
async def page_clients(request: Request):
    return _render("clients", request)


@router.get("/cases", response_class=HTMLResponse)
async def page_cases(request: Request):
    return _render("cases", request)


@router.get("/documents", response_class=HTMLResponse)
async def page_documents(request: Request):
    return _render("documents", request)


@router.get("/dockets", response_class=HTMLResponse)
async def page_dockets(request: Request):
    return _render("dockets", request)


@router.get("/schedules", response_class=HTMLResponse)
async def page_schedules(request: Request):
    return _render("schedules", request)


@router.get("/billing", response_class=HTMLResponse)
async def page_billing(request: Request):
    return _render("billing", request)


@router.get("/messages", response_class=HTMLResponse)
async def page_messages(request: Request):
    return _render("messages", request)


@router.get("/system", response_class=HTMLResponse)
async def page_system(request: Request):
    return _render("system", request)
