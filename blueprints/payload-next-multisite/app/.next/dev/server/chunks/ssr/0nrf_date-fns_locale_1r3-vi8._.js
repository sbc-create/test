module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "lt",
    ()=>lt
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/formatDistance.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/formatLong.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/formatRelative.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$localize$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/localize.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$match$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/match.js [app-rsc] (ecmascript)");
;
;
;
;
;
const lt = {
    code: "lt",
    formatDistance: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatDistance"],
    formatLong: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatLong"],
    formatRelative: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatRelative"],
    localize: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$localize$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["localize"],
    match: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$lt$2f$_lib$2f$match$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["match"],
    options: {
        weekStartsOn: 1 /* Monday */ ,
        firstWeekContainsDate: 4
    }
};
const __TURBOPACK__default__export__ = lt;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/formatDistance.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatDistance",
    ()=>formatDistance
]);
const translations = {
    xseconds_other: "sekundė_sekundžių_sekundes",
    xminutes_one: "minutė_minutės_minutę",
    xminutes_other: "minutės_minučių_minutes",
    xhours_one: "valanda_valandos_valandą",
    xhours_other: "valandos_valandų_valandas",
    xdays_one: "diena_dienos_dieną",
    xdays_other: "dienos_dienų_dienas",
    xweeks_one: "savaitė_savaitės_savaitę",
    xweeks_other: "savaitės_savaičių_savaites",
    xmonths_one: "mėnuo_mėnesio_mėnesį",
    xmonths_other: "mėnesiai_mėnesių_mėnesius",
    xyears_one: "metai_metų_metus",
    xyears_other: "metai_metų_metus",
    about: "apie",
    over: "daugiau nei",
    almost: "beveik",
    lessthan: "mažiau nei"
};
const translateSeconds = (_number, addSuffix, _key, isFuture)=>{
    if (!addSuffix) {
        return "kelios sekundės";
    } else {
        return isFuture ? "kelių sekundžių" : "kelias sekundes";
    }
};
const translateSingular = (_number, addSuffix, key, isFuture)=>{
    return !addSuffix ? forms(key)[0] : isFuture ? forms(key)[1] : forms(key)[2];
};
const translate = (number, addSuffix, key, isFuture)=>{
    const result = number + " ";
    if (number === 1) {
        return result + translateSingular(number, addSuffix, key, isFuture);
    } else if (!addSuffix) {
        return result + (special(number) ? forms(key)[1] : forms(key)[0]);
    } else {
        if (isFuture) {
            return result + forms(key)[1];
        } else {
            return result + (special(number) ? forms(key)[1] : forms(key)[2]);
        }
    }
};
function special(number) {
    return number % 10 === 0 || number > 10 && number < 20;
}
function forms(key) {
    return translations[key].split("_");
}
const formatDistanceLocale = {
    lessThanXSeconds: {
        one: translateSeconds,
        other: translate
    },
    xSeconds: {
        one: translateSeconds,
        other: translate
    },
    halfAMinute: "pusė minutės",
    lessThanXMinutes: {
        one: translateSingular,
        other: translate
    },
    xMinutes: {
        one: translateSingular,
        other: translate
    },
    aboutXHours: {
        one: translateSingular,
        other: translate
    },
    xHours: {
        one: translateSingular,
        other: translate
    },
    xDays: {
        one: translateSingular,
        other: translate
    },
    aboutXWeeks: {
        one: translateSingular,
        other: translate
    },
    xWeeks: {
        one: translateSingular,
        other: translate
    },
    aboutXMonths: {
        one: translateSingular,
        other: translate
    },
    xMonths: {
        one: translateSingular,
        other: translate
    },
    aboutXYears: {
        one: translateSingular,
        other: translate
    },
    xYears: {
        one: translateSingular,
        other: translate
    },
    overXYears: {
        one: translateSingular,
        other: translate
    },
    almostXYears: {
        one: translateSingular,
        other: translate
    }
};
const formatDistance = (token, count, options)=>{
    const adverb = token.match(/about|over|almost|lessthan/i);
    const unit = adverb ? token.replace(adverb[0], "") : token;
    const isFuture = options?.comparison !== undefined && options.comparison > 0;
    let result;
    const tokenValue = formatDistanceLocale[token];
    if (typeof tokenValue === "string") {
        result = tokenValue;
    } else if (count === 1) {
        result = tokenValue.one(count, options?.addSuffix === true, unit.toLowerCase() + "_one", isFuture);
    } else {
        result = tokenValue.other(count, options?.addSuffix === true, unit.toLowerCase() + "_other", isFuture);
    }
    if (adverb) {
        const key = adverb[0].toLowerCase();
        result = translations[key] + " " + result;
    }
    if (options?.addSuffix) {
        if (options.comparison && options.comparison > 0) {
            return "po " + result;
        } else {
            return "prieš " + result;
        }
    }
    return result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/formatLong.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatLong",
    ()=>formatLong
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildFormatLongFn.js [app-rsc] (ecmascript)");
;
const dateFormats = {
    full: "y 'm'. MMMM d 'd'., EEEE",
    long: "y 'm'. MMMM d 'd'.",
    medium: "y-MM-dd",
    short: "y-MM-dd"
};
const timeFormats = {
    full: "HH:mm:ss zzzz",
    long: "HH:mm:ss z",
    medium: "HH:mm:ss",
    short: "HH:mm"
};
const dateTimeFormats = {
    full: "{{date}} {{time}}",
    long: "{{date}} {{time}}",
    medium: "{{date}} {{time}}",
    short: "{{date}} {{time}}"
};
const formatLong = {
    date: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: dateFormats,
        defaultWidth: "full"
    }),
    time: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: timeFormats,
        defaultWidth: "full"
    }),
    dateTime: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: dateTimeFormats,
        defaultWidth: "full"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/formatRelative.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatRelative",
    ()=>formatRelative
]);
const formatRelativeLocale = {
    lastWeek: "'Praėjusį' eeee p",
    yesterday: "'Vakar' p",
    today: "'Šiandien' p",
    tomorrow: "'Rytoj' p",
    nextWeek: "eeee p",
    other: "P"
};
const formatRelative = (token, _date, _baseDate, _options)=>formatRelativeLocale[token];
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/localize.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "localize",
    ()=>localize
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildLocalizeFn.js [app-rsc] (ecmascript)");
;
const eraValues = {
    narrow: [
        "pr. Kr.",
        "po Kr."
    ],
    abbreviated: [
        "pr. Kr.",
        "po Kr."
    ],
    wide: [
        "prieš Kristų",
        "po Kristaus"
    ]
};
const quarterValues = {
    narrow: [
        "1",
        "2",
        "3",
        "4"
    ],
    abbreviated: [
        "I ketv.",
        "II ketv.",
        "III ketv.",
        "IV ketv."
    ],
    wide: [
        "I ketvirtis",
        "II ketvirtis",
        "III ketvirtis",
        "IV ketvirtis"
    ]
};
const formattingQuarterValues = {
    narrow: [
        "1",
        "2",
        "3",
        "4"
    ],
    abbreviated: [
        "I k.",
        "II k.",
        "III k.",
        "IV k."
    ],
    wide: [
        "I ketvirtis",
        "II ketvirtis",
        "III ketvirtis",
        "IV ketvirtis"
    ]
};
const monthValues = {
    narrow: [
        "S",
        "V",
        "K",
        "B",
        "G",
        "B",
        "L",
        "R",
        "R",
        "S",
        "L",
        "G"
    ],
    abbreviated: [
        "saus.",
        "vas.",
        "kov.",
        "bal.",
        "geg.",
        "birž.",
        "liep.",
        "rugp.",
        "rugs.",
        "spal.",
        "lapkr.",
        "gruod."
    ],
    wide: [
        "sausis",
        "vasaris",
        "kovas",
        "balandis",
        "gegužė",
        "birželis",
        "liepa",
        "rugpjūtis",
        "rugsėjis",
        "spalis",
        "lapkritis",
        "gruodis"
    ]
};
const formattingMonthValues = {
    narrow: [
        "S",
        "V",
        "K",
        "B",
        "G",
        "B",
        "L",
        "R",
        "R",
        "S",
        "L",
        "G"
    ],
    abbreviated: [
        "saus.",
        "vas.",
        "kov.",
        "bal.",
        "geg.",
        "birž.",
        "liep.",
        "rugp.",
        "rugs.",
        "spal.",
        "lapkr.",
        "gruod."
    ],
    wide: [
        "sausio",
        "vasario",
        "kovo",
        "balandžio",
        "gegužės",
        "birželio",
        "liepos",
        "rugpjūčio",
        "rugsėjo",
        "spalio",
        "lapkričio",
        "gruodžio"
    ]
};
const dayValues = {
    narrow: [
        "S",
        "P",
        "A",
        "T",
        "K",
        "P",
        "Š"
    ],
    short: [
        "Sk",
        "Pr",
        "An",
        "Tr",
        "Kt",
        "Pn",
        "Št"
    ],
    abbreviated: [
        "sk",
        "pr",
        "an",
        "tr",
        "kt",
        "pn",
        "št"
    ],
    wide: [
        "sekmadienis",
        "pirmadienis",
        "antradienis",
        "trečiadienis",
        "ketvirtadienis",
        "penktadienis",
        "šeštadienis"
    ]
};
const formattingDayValues = {
    narrow: [
        "S",
        "P",
        "A",
        "T",
        "K",
        "P",
        "Š"
    ],
    short: [
        "Sk",
        "Pr",
        "An",
        "Tr",
        "Kt",
        "Pn",
        "Št"
    ],
    abbreviated: [
        "sk",
        "pr",
        "an",
        "tr",
        "kt",
        "pn",
        "št"
    ],
    wide: [
        "sekmadienį",
        "pirmadienį",
        "antradienį",
        "trečiadienį",
        "ketvirtadienį",
        "penktadienį",
        "šeštadienį"
    ]
};
const dayPeriodValues = {
    narrow: {
        am: "pr. p.",
        pm: "pop.",
        midnight: "vidurnaktis",
        noon: "vidurdienis",
        morning: "rytas",
        afternoon: "diena",
        evening: "vakaras",
        night: "naktis"
    },
    abbreviated: {
        am: "priešpiet",
        pm: "popiet",
        midnight: "vidurnaktis",
        noon: "vidurdienis",
        morning: "rytas",
        afternoon: "diena",
        evening: "vakaras",
        night: "naktis"
    },
    wide: {
        am: "priešpiet",
        pm: "popiet",
        midnight: "vidurnaktis",
        noon: "vidurdienis",
        morning: "rytas",
        afternoon: "diena",
        evening: "vakaras",
        night: "naktis"
    }
};
const formattingDayPeriodValues = {
    narrow: {
        am: "pr. p.",
        pm: "pop.",
        midnight: "vidurnaktis",
        noon: "perpiet",
        morning: "rytas",
        afternoon: "popietė",
        evening: "vakaras",
        night: "naktis"
    },
    abbreviated: {
        am: "priešpiet",
        pm: "popiet",
        midnight: "vidurnaktis",
        noon: "perpiet",
        morning: "rytas",
        afternoon: "popietė",
        evening: "vakaras",
        night: "naktis"
    },
    wide: {
        am: "priešpiet",
        pm: "popiet",
        midnight: "vidurnaktis",
        noon: "perpiet",
        morning: "rytas",
        afternoon: "popietė",
        evening: "vakaras",
        night: "naktis"
    }
};
const ordinalNumber = (dirtyNumber, _options)=>{
    const number = Number(dirtyNumber);
    return number + "-oji";
};
const localize = {
    ordinalNumber,
    era: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: eraValues,
        defaultWidth: "wide"
    }),
    quarter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: quarterValues,
        defaultWidth: "wide",
        formattingValues: formattingQuarterValues,
        defaultFormattingWidth: "wide",
        argumentCallback: (quarter)=>quarter - 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: monthValues,
        defaultWidth: "wide",
        formattingValues: formattingMonthValues,
        defaultFormattingWidth: "wide"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayValues,
        defaultWidth: "wide",
        formattingValues: formattingDayValues,
        defaultFormattingWidth: "wide"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayPeriodValues,
        defaultWidth: "wide",
        formattingValues: formattingDayPeriodValues,
        defaultFormattingWidth: "wide"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt/_lib/match.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "match",
    ()=>match
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchFn.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchPatternFn.js [app-rsc] (ecmascript)");
;
;
const matchOrdinalNumberPattern = /^(\d+)(-oji)?/i;
const parseOrdinalNumberPattern = /\d+/i;
const matchEraPatterns = {
    narrow: /^p(r|o)\.?\s?(kr\.?|me)/i,
    abbreviated: /^(pr\.\s?(kr\.|m\.\s?e\.)|po\s?kr\.|mūsų eroje)/i,
    wide: /^(prieš Kristų|prieš mūsų erą|po Kristaus|mūsų eroje)/i
};
const parseEraPatterns = {
    wide: [
        /prieš/i,
        /(po|mūsų)/i
    ],
    any: [
        /^pr/i,
        /^(po|m)/i
    ]
};
const matchQuarterPatterns = {
    narrow: /^([1234])/i,
    abbreviated: /^(I|II|III|IV)\s?ketv?\.?/i,
    wide: /^(I|II|III|IV)\s?ketvirtis/i
};
const parseQuarterPatterns = {
    narrow: [
        /1/i,
        /2/i,
        /3/i,
        /4/i
    ],
    any: [
        /I$/i,
        /II$/i,
        /III/i,
        /IV/i
    ]
};
const matchMonthPatterns = {
    narrow: /^[svkbglr]/i,
    abbreviated: /^(saus\.|vas\.|kov\.|bal\.|geg\.|birž\.|liep\.|rugp\.|rugs\.|spal\.|lapkr\.|gruod\.)/i,
    wide: /^(sausi(s|o)|vasari(s|o)|kov(a|o)s|balandž?i(s|o)|gegužės?|birželi(s|o)|liep(a|os)|rugpjū(t|č)i(s|o)|rugsėj(is|o)|spali(s|o)|lapkri(t|č)i(s|o)|gruodž?i(s|o))/i
};
const parseMonthPatterns = {
    narrow: [
        /^s/i,
        /^v/i,
        /^k/i,
        /^b/i,
        /^g/i,
        /^b/i,
        /^l/i,
        /^r/i,
        /^r/i,
        /^s/i,
        /^l/i,
        /^g/i
    ],
    any: [
        /^saus/i,
        /^vas/i,
        /^kov/i,
        /^bal/i,
        /^geg/i,
        /^birž/i,
        /^liep/i,
        /^rugp/i,
        /^rugs/i,
        /^spal/i,
        /^lapkr/i,
        /^gruod/i
    ]
};
const matchDayPatterns = {
    narrow: /^[spatkš]/i,
    short: /^(sk|pr|an|tr|kt|pn|št)/i,
    abbreviated: /^(sk|pr|an|tr|kt|pn|št)/i,
    wide: /^(sekmadien(is|į)|pirmadien(is|į)|antradien(is|į)|trečiadien(is|į)|ketvirtadien(is|į)|penktadien(is|į)|šeštadien(is|į))/i
};
const parseDayPatterns = {
    narrow: [
        /^s/i,
        /^p/i,
        /^a/i,
        /^t/i,
        /^k/i,
        /^p/i,
        /^š/i
    ],
    wide: [
        /^se/i,
        /^pi/i,
        /^an/i,
        /^tr/i,
        /^ke/i,
        /^pe/i,
        /^še/i
    ],
    any: [
        /^sk/i,
        /^pr/i,
        /^an/i,
        /^tr/i,
        /^kt/i,
        /^pn/i,
        /^št/i
    ]
};
const matchDayPeriodPatterns = {
    narrow: /^(pr.\s?p.|pop.|vidurnaktis|(vidurdienis|perpiet)|rytas|(diena|popietė)|vakaras|naktis)/i,
    any: /^(priešpiet|popiet$|vidurnaktis|(vidurdienis|perpiet)|rytas|(diena|popietė)|vakaras|naktis)/i
};
const parseDayPeriodPatterns = {
    narrow: {
        am: /^pr/i,
        pm: /^pop./i,
        midnight: /^vidurnaktis/i,
        noon: /^(vidurdienis|perp)/i,
        morning: /rytas/i,
        afternoon: /(die|popietė)/i,
        evening: /vakaras/i,
        night: /naktis/i
    },
    any: {
        am: /^pr/i,
        pm: /^popiet$/i,
        midnight: /^vidurnaktis/i,
        noon: /^(vidurdienis|perp)/i,
        morning: /rytas/i,
        afternoon: /(die|popietė)/i,
        evening: /vakaras/i,
        night: /naktis/i
    }
};
const match = {
    ordinalNumber: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMatchPatternFn"])({
        matchPattern: matchOrdinalNumberPattern,
        parsePattern: parseOrdinalNumberPattern,
        valueCallback: (value)=>parseInt(value, 10)
    }),
    era: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchEraPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseEraPatterns,
        defaultParseWidth: "any"
    }),
    quarter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchQuarterPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseQuarterPatterns,
        defaultParseWidth: "any",
        valueCallback: (index)=>index + 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchMonthPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseMonthPatterns,
        defaultParseWidth: "any"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchDayPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseDayPatterns,
        defaultParseWidth: "any"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchDayPeriodPatterns,
        defaultMatchWidth: "any",
        parsePatterns: parseDayPeriodPatterns,
        defaultParseWidth: "any"
    })
};
}),
];

//# sourceMappingURL=0nrf_date-fns_locale_1r3-vi8._.js.map