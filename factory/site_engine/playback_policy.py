"""Разрешение перечня идентификаторов, которыми можно адресовать плеер.

Задача модуля — сделать вопрос «вправе ли мы адресовать плеер этим
идентификатором» одним ответом в одном месте, вместо константы, повторённой в
сборщике каталога, в сборщике разметки и в классификаторе причин.

Почему это оказалось нужно. Идентификатор был добавлен в перечень источника,
каталог получил 645 дескрипторов — а страницы всё равно показывали заглушку,
потому что сборщик плеера отвергал их по правилу контракта. Дефект выглядел как
исправление ровно потому, что перечней было два и разъехаться им ничто не
мешало.

Устройство:

* основа берётся из ПОЛУЧЕННОГО документа поставщика и здесь не дублируется;
* config/playback-identifiers.yaml вправе только сузить основу или включить
  идентификатор, у которого есть запись авторизации;
* идентификатор вне основы без authorization.status == "granted" не включается
  ни флагом в файле, ни переменной окружения — ворота отвечают отказом, а не
  тихим расширением перечня;
* автоматического отката к неподтверждённому идентификатору нет: отсутствие
  разрешённого — это причина, а не повод подставить другой.

Отказ здесь громкий намеренно. Молчаливое сужение перечня выглядит как
«видео просто нет» и разбирается неделями; исключение указывает на файл и
правило сразу.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

POLICY_REF = "config/playback-identifiers.yaml"
DEFAULT_PROVIDER = "cdnvideohub"

#: Где лежит полученный документ поставщика, если настройки эксплуатации рядом
#: нет. Имя поставщика — это имя каталога: перечислять поставщиков в
#: универсальном модуле значило бы вписать в ядро знание о конкретных из них.
CONTRACT_TEMPLATE = "knowledge/{provider}/PLAYER_CONTRACT.yaml"

#: Значения authorization.status, при которых идентификатор вне основы вправе
#: быть включён. Остальные значения читаются как «разрешения нет».
GRANTED = "granted"


class PlaybackPolicyError(RuntimeError):
    """Настройка перечня противоречит контракту поставщика."""

    status = "BLOCKED_PLAYER_CONTRACT"


@dataclass(frozen=True)
class Решение:
    """Итог разрешения перечня для конкретной точки применения."""

    provider: str
    allowed: tuple[str, ...]
    baseline: tuple[str, ...]
    policy_version: str
    contract_version: str
    site_profile: str | None = None
    content_type: str | None = None
    #: Включено сверх основы — всегда только с авторизацией.
    beyond_baseline: tuple[str, ...] = field(default_factory=tuple)
    #: Убрано из основы настройкой эксплуатации.
    disabled: tuple[str, ...] = field(default_factory=tuple)
    #: Отсеяно областью применения (профиль сайта или тип содержимого).
    out_of_scope: tuple[str, ...] = field(default_factory=tuple)

    def permits(self, identifier: str) -> bool:
        return identifier in self.allowed

    def reason_for(self, identifier: str) -> str | None:
        """Код причины, по которому идентификатор не подходит. None — подходит.

        Разные коды нужны не для красоты отчёта: «запрещено контрактом» решается
        обращением к владельцу контракта, «выключено настройкой» — правкой
        файла, «вне области» — расширением области. Один общий код заставил бы
        оператора выяснять это заново на каждой карточке.
        """
        if identifier in self.allowed:
            return None
        if identifier in self.out_of_scope:
            return "IDENTIFIER_OUT_OF_SCOPE"
        if identifier in self.disabled:
            return "IDENTIFIER_DISABLED_BY_POLICY"
        return "IDENTIFIER_FORBIDDEN_BY_CONTRACT"

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "allowed": list(self.allowed),
            "baseline": list(self.baseline),
            "policyVersion": self.policy_version,
            "contractVersion": self.contract_version,
            "siteProfile": self.site_profile,
            "contentType": self.content_type,
            "beyondBaseline": list(self.beyond_baseline),
            "disabled": list(self.disabled),
            "outOfScope": list(self.out_of_scope),
        }


def _root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    from factory.paths import PATHS

    return PATHS.root


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise PlaybackPolicyError(f"нет файла {path}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as ошибка:
        raise PlaybackPolicyError(f"{path} не читается как YAML: {ошибка}") from ошибка
    if not isinstance(loaded, dict):
        raise PlaybackPolicyError(f"{path} обязан быть отображением")
    return loaded


def baseline_from_contract(contract: dict, attribute: str) -> tuple[str, ...]:
    """Основа читается из контракта, а не из кода: копия неизбежно отстанет."""
    for запись in contract.get("attributes") or []:
        if isinstance(запись, dict) and запись.get("name") == attribute:
            allowed = запись.get("allowed")
            if not isinstance(allowed, list) or not allowed:
                raise PlaybackPolicyError(
                    f"в контракте у атрибута {attribute!r} пустой перечень allowed"
                )
            return tuple(str(значение) for значение in allowed)
    raise PlaybackPolicyError(f"в контракте нет атрибута {attribute!r}")


def _scope_permits(scope: Any, *, site_profile: str | None, content_type: str | None) -> bool:
    """Пустой перечень означает «без ограничения», а не «ничего не разрешено».

    Различие существенное: пустой список — это ненастроенное ограничение,
    и трактовать его как запрет значило бы выключить базовый перечень целиком
    при первой же опечатке.
    """
    if not isinstance(scope, dict):
        return True

    def подходит(перечень, значение) -> bool:
        # Ограничение считается заданным только когда в нём что-то есть.
        if not isinstance(перечень, list) or not перечень or значение is None:
            return True
        return значение in перечень

    return подходит(scope.get("site_profiles"), site_profile) and подходит(
        scope.get("content_types"), content_type
    )


def _flag_enabled(запись: dict, env: dict[str, str] | None) -> bool:
    """Переменная окружения вправе только выключить или включить флаг.

    Обойти проверку авторизации она не может: та выполняется отдельно и после.
    """
    включено = bool(запись.get("enabled"))
    имя = запись.get("flag")
    if env is not None and isinstance(имя, str) and имя in env:
        значение = str(env[имя]).strip().lower()
        включено = значение in {"1", "true", "yes", "on"}
    return включено


def _только_основа(
    provider: str, корень: Path, site_profile: str | None, content_type: str | None
) -> Решение:
    """Перечень при отсутствующей настройке — ровно основа из контракта."""
    ссылка = CONTRACT_TEMPLATE.format(provider=provider)
    if not (корень / ссылка).exists():
        raise PlaybackPolicyError(
            f"нет ни {POLICY_REF}, ни контракта {ссылка} для поставщика {provider!r}"
        )
    контракт = _read_yaml(корень / ссылка)
    основа = baseline_from_contract(контракт, "data-aggregator")
    return Решение(
        provider=provider,
        allowed=основа,
        baseline=основа,
        policy_version="baseline",
        contract_version=str(контракт.get("contract_version") or ""),
        site_profile=site_profile,
        content_type=content_type,
    )


def resolve(
    provider: str = DEFAULT_PROVIDER,
    *,
    site_profile: str | None = None,
    content_type: str | None = None,
    root: Path | None = None,
    env: dict[str, str] | None = None,
) -> Решение:
    """Перечень идентификаторов, допустимых в этой точке применения."""
    корень = _root(root)
    файл_политики = корень / POLICY_REF
    if not файл_политики.exists():
        return _только_основа(provider, корень, site_profile, content_type)
    политика = _read_yaml(файл_политики)
    поставщики = политика.get("providers")
    if not isinstance(поставщики, dict) or provider not in поставщики:
        raise PlaybackPolicyError(f"поставщик {provider!r} не описан в {POLICY_REF}")
    описание = поставщики[provider]
    if not isinstance(описание, dict):
        raise PlaybackPolicyError(f"описание поставщика {provider!r} обязано быть отображением")

    contract_ref = описание.get("contract_ref")
    if not isinstance(contract_ref, str) or not contract_ref:
        raise PlaybackPolicyError(f"у поставщика {provider!r} не указан contract_ref")
    контракт = _read_yaml(корень / contract_ref)

    заявленная = описание.get("contract_version")
    фактическая = контракт.get("contract_version")
    if заявленная and фактическая and str(заявленная) != str(фактическая):
        raise PlaybackPolicyError(
            f"настройка ссылается на версию контракта {заявленная!r}, "
            f"а файл содержит {фактическая!r}: перечень разрешён по устаревшему документу"
        )

    основа = baseline_from_contract(
        контракт, описание.get("baseline_attribute") or "data-aggregator"
    )
    идентификаторы = описание.get("identifiers")
    if not isinstance(идентификаторы, dict):
        raise PlaybackPolicyError(f"у поставщика {provider!r} нет раздела identifiers")

    разрешены: list[str] = []
    сверх: list[str] = []
    выключены: list[str] = []
    вне_области: list[str] = []

    for имя, запись in идентификаторы.items():
        имя = str(имя)
        if not isinstance(запись, dict):
            raise PlaybackPolicyError(f"описание идентификатора {имя!r} обязано быть отображением")
        включён = _flag_enabled(запись, env)
        в_основе = имя in основа

        if not включён:
            if в_основе:
                выключены.append(имя)
            continue

        if not в_основе:
            # Ворота соответствия. Включить идентификатор вне основы без записи
            # авторизации нельзя ни файлом, ни переменной окружения.
            авторизация = запись.get("authorization")
            статус = авторизация.get("status") if isinstance(авторизация, dict) else None
            if статус != GRANTED:
                raise PlaybackPolicyError(
                    f"идентификатор {имя!r} включён, но отсутствует в перечне контракта "
                    f"{tuple(основа)} и не имеет authorization.status == {GRANTED!r} "
                    f"(указано {статус!r}). Включение запрещено воротами соответствия: "
                    f"снять запрет вправе только владелец контракта."
                )
            сверх.append(имя)

        if not _scope_permits(
            запись.get("scope"), site_profile=site_profile, content_type=content_type
        ):
            вне_области.append(имя)
            continue

        разрешены.append(имя)

    # Идентификатор из основы, вовсе не упомянутый в настройке, остаётся
    # разрешённым: настройка сужает основу явно, а не забывчивостью.
    for имя in основа:
        if имя not in идентификаторы and имя not in разрешены:
            разрешены.append(имя)

    # Порядок основы — это приоритет из контракта, и терять его нельзя.
    упорядочены = [имя for имя in основа if имя in разрешены]
    упорядочены += [имя for имя in разрешены if имя not in основа]

    return Решение(
        provider=provider,
        allowed=tuple(упорядочены),
        baseline=tuple(основа),
        policy_version=str(политика.get("policy_version") or "0"),
        contract_version=str(фактическая or ""),
        site_profile=site_profile,
        content_type=content_type,
        beyond_baseline=tuple(сверх),
        disabled=tuple(выключены),
        out_of_scope=tuple(вне_области),
    )


#: Кэш по времени изменения обоих файлов. Разрешение вызывается на каждую
#: карточку каталога — а их пятьдесят три тысячи; читать YAML столько же раз
#: значит превратить сборку в чтение файлов. Ключ включает mtime, поэтому
#: правка настройки подхватывается без перезапуска.
_КЭШ: dict[tuple, Решение] = {}


def resolve_cached(
    provider: str = DEFAULT_PROVIDER,
    *,
    site_profile: str | None = None,
    content_type: str | None = None,
    root: Path | None = None,
    env: dict[str, str] | None = None,
) -> Решение:
    корень = _root(root)
    файл = корень / POLICY_REF
    try:
        отпечаток = файл.stat().st_mtime_ns
    except OSError:
        отпечаток = 0
    ключ = (
        str(корень),
        отпечаток,
        provider,
        site_profile,
        content_type,
        tuple(sorted(env.items())) if env else None,
    )
    if ключ not in _КЭШ:
        _КЭШ[ключ] = resolve(
            provider,
            site_profile=site_profile,
            content_type=content_type,
            root=root,
            env=env,
        )
    return _КЭШ[ключ]


def сбросить_кэш() -> None:
    _КЭШ.clear()
