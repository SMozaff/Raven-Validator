import json
from raven_validator.services.import_service import ImportService


def test_targeter_import_never_falls_back_to_github_url(tmp_path):
    p=tmp_path/'x.json'
    p.write_text(json.dumps({"schema":"raven-discovery-export-v1","discoveries":[{"title":"u/r","source_url":"https://github.com/u/r","provider":"openai","candidate_endpoints":[]}]}))
    r=ImportService().import_raven_targeter(p)
    assert r.imported==0
    assert r.skipped==1


def test_targeter_import_uses_real_candidate_endpoint(tmp_path):
    p=tmp_path/'x.json'
    p.write_text(json.dumps({"schema":"raven-discovery-export-v1","discoveries":[{"title":"u/r","source_url":"https://github.com/u/r","provider":"openai","candidate_endpoints":[{"url":"https://api.example.com/v1","evidence":"README"}]}]}))
    r=ImportService().import_raven_targeter(p)
    assert r.imported==1
    assert str(r.candidates[0].base_url).startswith('https://api.example.com/v1')
    assert str(r.candidates[0].source_url)=='https://github.com/u/r'
