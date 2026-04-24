"""Python rewrite surface for gateway server-method handlers."""

from .connect import connect_handlers
from .commands import commands_handlers
from .config import config_handlers
from .channels import channels_handlers
from .sessions import sessions_handlers
from .chat import chat_handlers
from .agent import agent_handlers
from .agents import agents_handlers
from .send import send_handlers
from .skills import skills_handlers
from .system import system_handlers
from .cron import cron_handlers
from .devices import device_handlers
from .models import models_handlers
from .models_auth_status import models_auth_status_handlers
from .push import push_handlers
from .update import update_handlers
from .voicewake import voicewake_handlers
from .wizard import wizard_handlers
from .tts import tts_handlers
from .web import web_handlers
from .tools_catalog import tools_catalog_handlers
from .tools_effective import tools_effective_handlers
from .talk import talk_handlers
from .usage import usage_handlers
from .exec_approvals import exec_approvals_handlers
from .nodes_pending import node_pending_handlers
from .nodes import node_handlers
from .health import health_handlers
from .logs import logs_handlers
from .image import image_handlers
from .doctor import doctor_handlers

__all__ = [
    "connect_handlers",
    "commands_handlers",
    "config_handlers",
    "channels_handlers",
    "sessions_handlers",
    "chat_handlers",
    "agent_handlers",
    "agents_handlers",
    "send_handlers",
    "skills_handlers",
    "system_handlers",
    "cron_handlers",
    "device_handlers",
    "models_handlers",
    "models_auth_status_handlers",
    "push_handlers",
    "update_handlers",
    "voicewake_handlers",
    "wizard_handlers",
    "tts_handlers",
    "web_handlers",
    "tools_catalog_handlers",
    "tools_effective_handlers",
    "talk_handlers",
    "usage_handlers",
    "exec_approvals_handlers",
    "node_pending_handlers",
    "node_handlers",
    "health_handlers",
    "logs_handlers",
    "image_handlers",
    "doctor_handlers",
]

