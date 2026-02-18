"""Auto-registration of all checks."""

from docops.checks.passive_voice import PassiveVoiceCheck
from docops.checks.formatting import (
    HeadingHierarchyCheck,
    HeadingCasingCheck,
    LineLengthCheck,
    ListConsistencyCheck,
    CodeBlockLanguageCheck,
)
from docops.checks.aws_keys import AwsKeyCheck
from docops.checks.pii import PiiCheck
from docops.checks.terminology import TerminologyCheck
from docops.checks.docc_checks import (
    DoccMissingDescriptionCheck,
    DoccStalePlatformCheck,
    DoccBrokenCrossrefCheck,
    DoccTerminologyCheck,
)

__register__ = [
    PassiveVoiceCheck(),
    HeadingHierarchyCheck(),
    HeadingCasingCheck(),
    LineLengthCheck(),
    ListConsistencyCheck(),
    CodeBlockLanguageCheck(),
    AwsKeyCheck(),
    PiiCheck(),
    TerminologyCheck(),
    DoccMissingDescriptionCheck(),
    DoccStalePlatformCheck(),
    DoccBrokenCrossrefCheck(),
    DoccTerminologyCheck(),
]
