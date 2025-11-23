"""태그 이름을 받아 Minecraft tag JSON을 재귀적으로 탐색해 실제 아이템 이름 목록을 반환합니다.

사용 예:
    from search_tag import search_tag
    items = search_tag("diamond_tool_materials")  # ['diamond']

규칙:
- 파일 구조: craft_or_smelt/tags/**/<tag>.json
- JSON 형식: {"values": [ ... ]}
- values 요소가 "minecraft:<item>" 형태면 접두사 제거 후 결과 목록에 추가
- values 요소가 "#minecraft:<othertag>" 형태면 해당 태그 파일을 찾아 동일 규칙으로 재귀 처리
- 순환 참조를 방지하기 위해 방문한 태그는 재처리하지 않음
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Set, Optional
import json

# 기본 tags 디렉터리 (이 파일과 같은 디렉터리 내부의 'tags')
_DEFAULT_TAGS_DIR = Path(__file__).resolve().parent / "tags"

class TagNotFoundError(FileNotFoundError):
    """요청한 태그 파일을 찾을 수 없을 때 발생."""
    pass


def _find_tag_file(tag: str, base_dir: Path) -> Optional[Path]:
    """tags 디렉터리 아래 재귀적으로 <tag>.json 파일을 찾는다.

    여러 위치(item/, block/ 등)에 있을 수 있으므로 처음 발견한 파일을 반환.
    없으면 None.
    """
    pattern = f"**/{tag}.json"
    # glob은 Path.rglob 사용
    for p in base_dir.rglob(f"{tag}.json"):
        if p.is_file():
            return p
    return None


def _parse_tag_file(file_path: Path) -> List[str]:
    """태그 JSON 파일을 로드하고 values 리스트를 반환.
    잘못된 포맷은 빈 리스트 처리.
    """
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    values = data.get("values")
    if not isinstance(values, list):
        return []
    # 문자열만 필터링
    return [v for v in values if isinstance(v, str)]


def search_tag(tag: str, base_dir: Optional[Path] = None, _visited: Optional[Set[str]] = None) -> List[str]:
    """주어진 태그 이름을 해석하여 포함하는 모든 아이템(접두사 없는 이름) 리스트를 반환.

    매개변수:
        tag: 태그 이름 (예: 'diamond_tool_materials')
        base_dir: tags 루트 디렉터리 (기본값은 현재 파일 기준 ./tags)
    반환:
        아이템 문자열 리스트 (중복 허용; 필요시 set 처리 가능)
    예외:
        TagNotFoundError: 태그 파일을 찾지 못한 경우
    """
    if base_dir is None:
        base_dir = _DEFAULT_TAGS_DIR

    if _visited is None:
        _visited = set()

    if tag in _visited:
        # 순환 참조로 인해 이미 처리한 태그는 빈 결과 (또는 무시)
        return []
    _visited.add(tag)

    file_path = _find_tag_file(tag, base_dir)
    if file_path is None:
        raise TagNotFoundError(f"Tag file not found for tag: {tag}")

    raw_values = _parse_tag_file(file_path)
    results: List[str] = []

    for val in raw_values:
        if val.startswith("#minecraft:"):
            # 태그 참조 -> 재귀 확장
            nested_tag = val.split(":", 1)[1]
            results.extend(search_tag(nested_tag, base_dir=base_dir, _visited=_visited))
        elif val.startswith("minecraft:"):
            item = val.split(":", 1)[1]
            results.append(item)
        else:
            # 명시되지 않은 포맷: 그대로 추가할지 결정. 여기서는 무시 또는 원문 추가 선택 가능.
            # 사양에 없으므로 무시.
            pass

    return list(dict.fromkeys(results))

if __name__ == "__main__":  # 간단한 CLI 사용
    print(search_tag("planks")[0])

