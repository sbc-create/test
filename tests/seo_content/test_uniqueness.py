"""Уникальность, каннибализация и doorway-риск.

Проверяется не «процент уникальности», а способность поймать конкретные
способы размножить один текст: побайтовую копию, копию с другой пунктуацией,
копию с переставленными формами слов, копию с подменённым названием и общую
цепочку слов. Каждый способ ловится своим измерителем, и ни один измеритель
не назначен единственным.
"""
from __future__ import annotations

import pytest

from factory.seo_content import dedup as D

ОРИГИНАЛ = ("«Тихая гавань» — сериал 2019 года производства России. В центре "
            "истории — смотритель маяка Вера Ильина; действие происходит на "
            "острове с одним причалом. Заявленные жанры — драма и детектив.")


def корпус(*тексты, site="seo-test-0002", names=("Тихая гавань",)):
    return [D.CorpusEntry(entry_id=f"e{i}", site_id=site, entity_type="title",
                          entity_id=f"t{i}", text=т, names=names)
            for i, т in enumerate(тексты)]


def проверить(текст, корпус_записей, *, site="seo-test-0001",
              entity="title-0001", names=("Тихая гавань",)):
    return D.NearDuplicateDetector(корпус_записей).check(
        текст, site_id=site, entity_id=entity, names=names,
        allowed_titles=names)


class TestТочныеИПочтиТочныеКопии:
    def test_побайтовая_копия(self):
        о = проверить(ОРИГИНАЛ, корпус(ОРИГИНАЛ))
        assert о.exact_duplicates == 1 and о.blocked

    def test_копия_с_другой_пунктуацией(self):
        изменённая = ОРИГИНАЛ.replace("—", "-").replace(";", ",").upper()
        о = проверить(изменённая, корпус(ОРИГИНАЛ))
        assert о.normalized_duplicates == 1 and о.blocked

    def test_копия_с_переставленными_формами(self):
        """Перестановка слов и смена окончаний — не новый текст."""
        слова = ОРИГИНАЛ.split()
        переставленная = " ".join(reversed(слова))
        о = проверить(переставленная, корпус(ОРИГИНАЛ))
        assert о.normalized_duplicates == 1 and о.blocked

    def test_межсайтовая_копия_с_подменой_названия(self):
        чужая = ОРИГИНАЛ.replace("Тихая гавань", "Шумная бухта")
        о = проверить(чужая, корпус(ОРИГИНАЛ), names=("Шумная бухта",))
        assert о.cross_site_template_copies == 1 and о.blocked

    def test_совпадающая_цепочка_от_двенадцати_слов(self):
        другой = ("«Медный ключ» — фильм 2021 года. В центре истории — "
                  "смотритель маяка Вера Ильина; действие происходит на "
                  "острове с одним причалом.")
        о = проверить(другой, корпус(ОРИГИНАЛ), names=("Медный ключ",))
        assert о.long_run_matches >= 1 and о.blocked

    def test_название_из_двенадцати_слов_не_считается_заимствованием(self):
        длинное = ("Обратный отсчёт в Кимже: полная хроника второй навигации "
                   "и всего, что за ней последовало")
        а = f"«{длинное}» — сериал 2019 года."
        б = f"«{длинное}» — фильм 2024 года."
        о = D.NearDuplicateDetector(
            корпус(б, names=(длинное,))).check(
            а, site_id="seo-test-0001", entity_id="t-a", names=(длинное,),
            allowed_titles=(длинное,))
        assert о.long_run_matches == 0

    def test_свой_же_одобренный_текст_дублем_не_считается(self):
        свой = [D.CorpusEntry("e0", "seo-test-0001", "title", "title-0001",
                              ОРИГИНАЛ, kind="approved",
                              names=("Тихая гавань",))]
        о = проверить(ОРИГИНАЛ, свой)
        assert not о.blocked


class TestНезависимыеИзмерители:
    def test_пять_грамм_ловят_пересказ(self):
        пересказ = ОРИГИНАЛ.replace("В центре истории", "В центре сюжета")
        о = проверить(пересказ, корпус(ОРИГИНАЛ), names=("Тихая гавань",))
        assert о.blocked or о.review_required

    def test_minhash_и_simhash_считаются(self):
        а, б = ОРИГИНАЛ, ОРИГИНАЛ.replace("драма", "мелодрама")
        assert D.minhash_similarity(D.minhash(а), D.minhash(б)) > 0.8
        assert D.hamming(D.simhash(а), D.simhash(б)) < 12

    def test_разные_тексты_не_объявляются_дублями(self):
        другой = ("«Медный ключ» — документальный фильм 2005 года о работе "
                  "речного порта в межсезонье.")
        о = проверить(другой, корпус(ОРИГИНАЛ), names=("Медный ключ",))
        assert not о.blocked and о.review_required == 0

    def test_семантика_не_объявляется_измеренной(self):
        о = проверить(ОРИГИНАЛ, корпус("совсем другой текст"))
        assert о.semantic_status == "NOT_EVALUATED"
        assert "embeddings" in о.semantic_reason


class TestПовторяющиесяВступления:
    def test_одинаковые_зачины_видны(self):
        """Одинаковы первые шестьдесят символов — значит, одинаково и
        вступление, каким его видит читатель."""
        тексты = [f"Перед вами подробный разбор произведения из каталога. "
                  f"Работа номер {i} отличается только этим." for i in range(50)]
        о = D.corpus_patterns(тексты)
        assert о.repeated_opening_rate > 0.02 and not о.within_budget

    def test_разные_зачины_укладываются_в_бюджет(self):
        тексты = [f"«Работа {i}» — {'сериал' if i % 2 else 'фильм'} "
                  f"{2000 + i} года производства России." for i in range(50)]
        assert D.corpus_patterns(тексты).within_budget

    def test_рамка_считается_отдельно_от_вступления(self):
        """Страницы серий по устройству начинаются одинаково. Это отдельная
        мера, и подменять ею бюджет вступлений нельзя."""
        тексты = [f"Серия {i} 1-го сезона «Работа {i}»." for i in range(20)]
        о = D.corpus_patterns(тексты, [(f"Работа {i}",) for i in range(20)])
        assert о.repeated_frame_rate > о.repeated_opening_rate


class TestDoorway:
    def test_тот_же_каталог_без_своего_угла(self):
        уровень, пояснение = D.doorway_risk(
            site_id="seo-test-0001", own_angle=None,
            sibling_sites=["a", "b", "c"], same_catalog=True)
        assert уровень == "HIGH"
        assert "noindex" in пояснение or "канониз" in пояснение

    def test_собственный_угол_снимает_риск(self):
        уровень, _ = D.doorway_risk(
            site_id="seo-test-0001", own_angle="разбор устройства производства",
            sibling_sites=["a", "b"], same_catalog=True)
        assert уровень == "NONE"

    def test_без_объявленного_угла_риск_не_нулевой(self):
        уровень, _ = D.doorway_risk(site_id="s", own_angle=None,
                                    sibling_sites=[], same_catalog=False)
        assert уровень == "MEDIUM"


class TestМаскированиеЛичности:
    def test_маска_снимает_имя_и_число(self):
        замаскированный = D.mask_identity(
            "«Тихая гавань» 2019 года, 3 сезона", names=("Тихая гавань",))
        assert "Тихая" not in замаскированный and "2019" not in замаскированный

    def test_маска_работает_по_основе(self):
        assert "〈ИМЯ〉" in D.mask_identity("в «Бункере» темно", names=("Бункер",))
