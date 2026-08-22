module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "is",
    ()=>is
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/formatDistance.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/formatLong.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/formatRelative.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$localize$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/localize.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$match$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/match.js [app-rsc] (ecmascript)");
;
;
;
;
;
const is = {
    code: "is",
    formatDistance: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatDistance"],
    formatLong: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatLong"],
    formatRelative: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatRelative"],
    localize: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$localize$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["localize"],
    match: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$is$2f$_lib$2f$match$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["match"],
    options: {
        weekStartsOn: 1 /* Monday */ ,
        firstWeekContainsDate: 4
    }
};
const __TURBOPACK__default__export__ = is;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/formatDistance.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatDistance",
    ()=>formatDistance
]);
const formatDistanceLocale = {
    lessThanXSeconds: {
        one: "minna en 1 sekúnda",
        other: "minna en {{count}} sekúndur"
    },
    xSeconds: {
        one: "1 sekúnda",
        other: "{{count}} sekúndur"
    },
    halfAMinute: "hálf mínúta",
    lessThanXMinutes: {
        one: "minna en 1 mínúta",
        other: "minna en {{count}} mínútur"
    },
    xMinutes: {
        one: "1 mínúta",
        other: "{{count}} mínútur"
    },
    aboutXHours: {
        one: "u.þ.b. 1 klukkustund",
        other: "u.þ.b. {{count}} klukkustundir"
    },
    xHours: {
        one: "1 klukkustund",
        other: "{{count}} klukkustundir"
    },
    xDays: {
        one: "1 dagur",
        other: "{{count}} dagar"
    },
    aboutXWeeks: {
        one: "um viku",
        other: "um {{count}} vikur"
    },
    xWeeks: {
        one: "1 viku",
        other: "{{count}} vikur"
    },
    aboutXMonths: {
        one: "u.þ.b. 1 mánuður",
        other: "u.þ.b. {{count}} mánuðir"
    },
    xMonths: {
        one: "1 mánuður",
        other: "{{count}} mánuðir"
    },
    aboutXYears: {
        one: "u.þ.b. 1 ár",
        other: "u.þ.b. {{count}} ár"
    },
    xYears: {
        one: "1 ár",
        other: "{{count}} ár"
    },
    overXYears: {
        one: "meira en 1 ár",
        other: "meira en {{count}} ár"
    },
    almostXYears: {
        one: "næstum 1 ár",
        other: "næstum {{count}} ár"
    }
};
const formatDistance = (token, count, options)=>{
    let result;
    const tokenValue = formatDistanceLocale[token];
    if (typeof tokenValue === "string") {
        result = tokenValue;
    } else if (count === 1) {
        result = tokenValue.one;
    } else {
        result = tokenValue.other.replace("{{count}}", count.toString());
    }
    if (options?.addSuffix) {
        if (options.comparison && options.comparison > 0) {
            return "í " + result;
        } else {
            return result + " síðan";
        }
    }
    return result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/formatLong.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatLong",
    ()=>formatLong
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildFormatLongFn.js [app-rsc] (ecmascript)");
;
const dateFormats = {
    full: "EEEE, do MMMM y",
    long: "do MMMM y",
    medium: "do MMM y",
    short: "d.MM.y"
};
const timeFormats = {
    full: "'kl'. HH:mm:ss zzzz",
    long: "HH:mm:ss z",
    medium: "HH:mm:ss",
    short: "HH:mm"
};
const dateTimeFormats = {
    full: "{{date}} 'kl.' {{time}}",
    long: "{{date}} 'kl.' {{time}}",
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
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/formatRelative.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatRelative",
    ()=>formatRelative
]);
const formatRelativeLocale = {
    lastWeek: "'síðasta' dddd 'kl.' p",
    yesterday: "'í gær kl.' p",
    today: "'í dag kl.' p",
    tomorrow: "'á morgun kl.' p",
    nextWeek: "dddd 'kl.' p",
    other: "P"
};
const formatRelative = (token, _date, _baseDate, _options)=>formatRelativeLocale[token];
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/localize.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "localize",
    ()=>localize
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildLocalizeFn.js [app-rsc] (ecmascript)");
;
const eraValues = {
    narrow: [
        "f.Kr.",
        "e.Kr."
    ],
    abbreviated: [
        "f.Kr.",
        "e.Kr."
    ],
    wide: [
        "fyrir Krist",
        "eftir Krist"
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
        "1F",
        "2F",
        "3F",
        "4F"
    ],
    wide: [
        "1. fjórðungur",
        "2. fjórðungur",
        "3. fjórðungur",
        "4. fjórðungur"
    ]
};
const monthValues = {
    narrow: [
        "J",
        "F",
        "M",
        "A",
        "M",
        "J",
        "J",
        "Á",
        "S",
        "Ó",
        "N",
        "D"
    ],
    abbreviated: [
        "jan.",
        "feb.",
        "mars",
        "apríl",
        "maí",
        "júní",
        "júlí",
        "ágúst",
        "sept.",
        "okt.",
        "nóv.",
        "des."
    ],
    wide: [
        "janúar",
        "febrúar",
        "mars",
        "apríl",
        "maí",
        "júní",
        "júlí",
        "ágúst",
        "september",
        "október",
        "nóvember",
        "desember"
    ]
};
const dayValues = {
    narrow: [
        "S",
        "M",
        "Þ",
        "M",
        "F",
        "F",
        "L"
    ],
    short: [
        "Su",
        "Má",
        "Þr",
        "Mi",
        "Fi",
        "Fö",
        "La"
    ],
    abbreviated: [
        "sun.",
        "mán.",
        "þri.",
        "mið.",
        "fim.",
        "fös.",
        "lau."
    ],
    wide: [
        "sunnudagur",
        "mánudagur",
        "þriðjudagur",
        "miðvikudagur",
        "fimmtudagur",
        "föstudagur",
        "laugardagur"
    ]
};
const dayPeriodValues = {
    narrow: {
        am: "f",
        pm: "e",
        midnight: "miðnætti",
        noon: "hádegi",
        morning: "morgunn",
        afternoon: "síðdegi",
        evening: "kvöld",
        night: "nótt"
    },
    abbreviated: {
        am: "f.h.",
        pm: "e.h.",
        midnight: "miðnætti",
        noon: "hádegi",
        morning: "morgunn",
        afternoon: "síðdegi",
        evening: "kvöld",
        night: "nótt"
    },
    wide: {
        am: "fyrir hádegi",
        pm: "eftir hádegi",
        midnight: "miðnætti",
        noon: "hádegi",
        morning: "morgunn",
        afternoon: "síðdegi",
        evening: "kvöld",
        night: "nótt"
    }
};
const formattingDayPeriodValues = {
    narrow: {
        am: "f",
        pm: "e",
        midnight: "á miðnætti",
        noon: "á hádegi",
        morning: "að morgni",
        afternoon: "síðdegis",
        evening: "um kvöld",
        night: "um nótt"
    },
    abbreviated: {
        am: "f.h.",
        pm: "e.h.",
        midnight: "á miðnætti",
        noon: "á hádegi",
        morning: "að morgni",
        afternoon: "síðdegis",
        evening: "um kvöld",
        night: "um nótt"
    },
    wide: {
        am: "fyrir hádegi",
        pm: "eftir hádegi",
        midnight: "á miðnætti",
        noon: "á hádegi",
        morning: "að morgni",
        afternoon: "síðdegis",
        evening: "um kvöld",
        night: "um nótt"
    }
};
const ordinalNumber = (dirtyNumber, _options)=>{
    const number = Number(dirtyNumber);
    return number + ".";
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
        argumentCallback: (quarter)=>quarter - 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: monthValues,
        defaultWidth: "wide"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayValues,
        defaultWidth: "wide"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayPeriodValues,
        defaultWidth: "wide",
        formattingValues: formattingDayPeriodValues,
        defaultFormattingWidth: "wide"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is/_lib/match.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "match",
    ()=>match
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchFn.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchPatternFn.js [app-rsc] (ecmascript)");
;
;
const matchOrdinalNumberPattern = /^(\d+)(\.)?/i;
const parseOrdinalNumberPattern = /\d+(\.)?/i;
const matchEraPatterns = {
    narrow: /^(f\.Kr\.|e\.Kr\.)/i,
    abbreviated: /^(f\.Kr\.|e\.Kr\.)/i,
    wide: /^(fyrir Krist|eftir Krist)/i
};
const parseEraPatterns = {
    any: [
        /^(f\.Kr\.)/i,
        /^(e\.Kr\.)/i
    ]
};
const matchQuarterPatterns = {
    narrow: /^[1234]\.?/i,
    abbreviated: /^q[1234]\.?/i,
    wide: /^[1234]\.? fjórðungur/i
};
const parseQuarterPatterns = {
    any: [
        /1\.?/i,
        /2\.?/i,
        /3\.?/i,
        /4\.?/i
    ]
};
const matchMonthPatterns = {
    narrow: /^[jfmásónd]/i,
    abbreviated: /^(jan\.|feb\.|mars\.|apríl\.|maí|júní|júlí|águst|sep\.|oct\.|nov\.|dec\.)/i,
    wide: /^(januar|febrúar|mars|apríl|maí|júní|júlí|águst|september|október|nóvember|desember)/i
};
const parseMonthPatterns = {
    narrow: [
        /^j/i,
        /^f/i,
        /^m/i,
        /^a/i,
        /^m/i,
        /^j/i,
        /^j/i,
        /^á/i,
        /^s/i,
        /^ó/i,
        /^n/i,
        /^d/i
    ],
    any: [
        /^ja/i,
        /^f/i,
        /^mar/i,
        /^ap/i,
        /^maí/i,
        /^jún/i,
        /^júl/i,
        /^áu/i,
        /^s/i,
        /^ó/i,
        /^n/i,
        /^d/i
    ]
};
const matchDayPatterns = {
    narrow: /^[smtwf]/i,
    short: /^(su|má|þr|mi|fi|fö|la)/i,
    abbreviated: /^(sun|mán|þri|mið|fim|fös|lau)\.?/i,
    wide: /^(sunnudagur|mánudagur|þriðjudagur|miðvikudagur|fimmtudagur|föstudagur|laugardagur)/i
};
const parseDayPatterns = {
    narrow: [
        /^s/i,
        /^m/i,
        /^þ/i,
        /^m/i,
        /^f/i,
        /^f/i,
        /^l/i
    ],
    any: [
        /^su/i,
        /^má/i,
        /^þr/i,
        /^mi/i,
        /^fi/i,
        /^fö/i,
        /^la/i
    ]
};
const matchDayPeriodPatterns = {
    narrow: /^(f|e|síðdegis|(á|að|um) (morgni|kvöld|nótt|miðnætti))/i,
    any: /^(fyrir hádegi|eftir hádegi|[ef]\.?h\.?|síðdegis|morgunn|(á|að|um) (morgni|kvöld|nótt|miðnætti))/i
};
const parseDayPeriodPatterns = {
    any: {
        am: /^f/i,
        pm: /^e/i,
        midnight: /^mi/i,
        noon: /^há/i,
        morning: /morgunn/i,
        afternoon: /síðdegi/i,
        evening: /kvöld/i,
        night: /nótt/i
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

//# sourceMappingURL=0nrf_date-fns_locale_1oh6hm3._.js.map