from outlook_mail_extractor.contracts.dependency_guard import DEPENDENCY_GUARD_EXIT_CODE
from outlook_mail_extractor.models import DependencyGuardError


def map_exception_to_exit_code(error: Exception) -> int:
    if isinstance(error, DependencyGuardError):
        return DEPENDENCY_GUARD_EXIT_CODE
    return 1
