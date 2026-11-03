from pathlib import Path
import re
import runpy
from unittest.mock import Mock

import pytest

from ok.core import skills

# [LINUX-PORT-CRITICAL] Linux 分支专属核心适配：技能白名单仅包含本地两个专属技能，合并时严禁覆盖
CONSUMER_SKILLS = {'combat-optimization', 'upstream-sync'}


def assert_skill_links_resolve(catalog):
    for skill in catalog:
        source = Path(skill['path'])
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                assert (source.parent / target.split('#')[0]).resolve().is_file(), target


def test_checkout_skills_are_discovered_independently_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    catalog = {skill['id']: skill for skill in skills.list_skills()}
    assert CONSUMER_SKILLS.issubset(catalog.keys())
    assert catalog['upstream-sync']['name'] == 'upstream-sync'
    for skill in catalog.values():
        assert skill['description']
        assert Path(skill['path']).is_absolute()
        assert skills.get_skill(skill['id'])['content'] == Path(skill['path']).read_text(encoding='utf-8')
    assert_skill_links_resolve([catalog[k] for k in CONSUMER_SKILLS])


def test_installed_skills_use_bundled_files(tmp_path, monkeypatch):
    package = tmp_path / 'ok'
    monkeypatch.setattr(skills, '__file__', str(package / 'core/skills.py'))
    skill = package / 'agent_resources/.agents/skills/example/SKILL.md'
    skill.parent.mkdir(parents=True)
    content = '---\nname: example\ndescription: Bundled example.\n---\nInstructions.\n'
    skill.write_text(content, encoding='utf-8')
    assert skills.list_skills() == [{
        'id': 'example', 'name': 'example', 'description': 'Bundled example.',
        'uri': 'ok-script://skills/example', 'path': str(skill),
    }]
    assert skills.get_skill('example')['content'] == content





@pytest.mark.parametrize('skill_id', ['missing', '../setup.py', '../../AGENTS.md', '/etc/passwd',
                                     'commit_changes', 'deploy_pip', 'compile_i18n'])
def test_unknown_skill_cannot_read_arbitrary_files(skill_id):
    with pytest.raises(ValueError, match='Unknown skill'):
        skills.get_skill(skill_id)
