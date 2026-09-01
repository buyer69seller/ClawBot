class ClawError(Exception):
    pass

class AuthError(ClawError):
    pass

class VersionMismatch(ClawError):
    pass

class GameEnded(ClawError):
    pass

class AgentDead(ClawError):
    pass

class ResumeTargetDead(ClawError):
    pass
