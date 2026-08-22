(globalThis["TURBOPACK"] || (globalThis["TURBOPACK"] = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "bn",
    ()=>bn,
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/formatDistance.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/formatLong.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/formatRelative.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$localize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/localize.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$match$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/match.js [app-client] (ecmascript)");
;
;
;
;
;
const bn = {
    code: "bn",
    formatDistance: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatDistance"],
    formatLong: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatLong"],
    formatRelative: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatRelative"],
    localize: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$localize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["localize"],
    match: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$match$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["match"],
    options: {
        weekStartsOn: 0 /* Sunday */ ,
        firstWeekContainsDate: 1
    }
};
const __TURBOPACK__default__export__ = bn;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/formatDistance.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatDistance",
    ()=>formatDistance
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$localize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/localize.js [app-client] (ecmascript)");
;
const formatDistanceLocale = {
    lessThanXSeconds: {
        one: "প্রায় ১ সেকেন্ড",
        other: "প্রায় {{count}} সেকেন্ড"
    },
    xSeconds: {
        one: "১ সেকেন্ড",
        other: "{{count}} সেকেন্ড"
    },
    halfAMinute: "আধ মিনিট",
    lessThanXMinutes: {
        one: "প্রায় ১ মিনিট",
        other: "প্রায় {{count}} মিনিট"
    },
    xMinutes: {
        one: "১ মিনিট",
        other: "{{count}} মিনিট"
    },
    aboutXHours: {
        one: "প্রায় ১ ঘন্টা",
        other: "প্রায় {{count}} ঘন্টা"
    },
    xHours: {
        one: "১ ঘন্টা",
        other: "{{count}} ঘন্টা"
    },
    xDays: {
        one: "১ দিন",
        other: "{{count}} দিন"
    },
    aboutXWeeks: {
        one: "প্রায় ১ সপ্তাহ",
        other: "প্রায় {{count}} সপ্তাহ"
    },
    xWeeks: {
        one: "১ সপ্তাহ",
        other: "{{count}} সপ্তাহ"
    },
    aboutXMonths: {
        one: "প্রায় ১ মাস",
        other: "প্রায় {{count}} মাস"
    },
    xMonths: {
        one: "১ মাস",
        other: "{{count}} মাস"
    },
    aboutXYears: {
        one: "প্রায় ১ বছর",
        other: "প্রায় {{count}} বছর"
    },
    xYears: {
        one: "১ বছর",
        other: "{{count}} বছর"
    },
    overXYears: {
        one: "১ বছরের বেশি",
        other: "{{count}} বছরের বেশি"
    },
    almostXYears: {
        one: "প্রায় ১ বছর",
        other: "প্রায় {{count}} বছর"
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
        result = tokenValue.other.replace("{{count}}", (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$bn$2f$_lib$2f$localize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["numberToLocale"])(count));
    }
    if (options?.addSuffix) {
        if (options.comparison && options.comparison > 0) {
            return result + " এর মধ্যে";
        } else {
            return result + " আগে";
        }
    }
    return result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/formatLong.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatLong",
    ()=>formatLong
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildFormatLongFn.js [app-client] (ecmascript)");
;
const dateFormats = {
    full: "EEEE, MMMM do, y",
    long: "MMMM do, y",
    medium: "MMM d, y",
    short: "MM/dd/yyyy"
};
const timeFormats = {
    full: "h:mm:ss a zzzz",
    long: "h:mm:ss a z",
    medium: "h:mm:ss a",
    short: "h:mm a"
};
const dateTimeFormats = {
    full: "{{date}} {{time}} 'সময়'",
    long: "{{date}} {{time}} 'সময়'",
    medium: "{{date}}, {{time}}",
    short: "{{date}}, {{time}}"
};
const formatLong = {
    date: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: dateFormats,
        defaultWidth: "full"
    }),
    time: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: timeFormats,
        defaultWidth: "full"
    }),
    dateTime: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: dateTimeFormats,
        defaultWidth: "full"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/formatRelative.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatRelative",
    ()=>formatRelative
]);
const formatRelativeLocale = {
    lastWeek: "'গত' eeee 'সময়' p",
    yesterday: "'গতকাল' 'সময়' p",
    today: "'আজ' 'সময়' p",
    tomorrow: "'আগামীকাল' 'সময়' p",
    nextWeek: "eeee 'সময়' p",
    other: "P"
};
const formatRelative = (token, _date, _baseDate, _options)=>formatRelativeLocale[token];
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/localize.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "localize",
    ()=>localize,
    "numberToLocale",
    ()=>numberToLocale
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildLocalizeFn.js [app-client] (ecmascript)");
;
const numberValues = {
    locale: {
        1: "১",
        2: "২",
        3: "৩",
        4: "৪",
        5: "৫",
        6: "৬",
        7: "৭",
        8: "৮",
        9: "৯",
        0: "০"
    },
    number: {
        "১": "1",
        "২": "2",
        "৩": "3",
        "৪": "4",
        "৫": "5",
        "৬": "6",
        "৭": "7",
        "৮": "8",
        "৯": "9",
        "০": "0"
    }
};
const eraValues = {
    narrow: [
        "খ্রিঃপূঃ",
        "খ্রিঃ"
    ],
    abbreviated: [
        "খ্রিঃপূর্ব",
        "খ্রিঃ"
    ],
    wide: [
        "খ্রিস্টপূর্ব",
        "খ্রিস্টাব্দ"
    ]
};
const quarterValues = {
    narrow: [
        "১",
        "২",
        "৩",
        "৪"
    ],
    abbreviated: [
        "১ত্রৈ",
        "২ত্রৈ",
        "৩ত্রৈ",
        "৪ত্রৈ"
    ],
    wide: [
        "১ম ত্রৈমাসিক",
        "২য় ত্রৈমাসিক",
        "৩য় ত্রৈমাসিক",
        "৪র্থ ত্রৈমাসিক"
    ]
};
const monthValues = {
    narrow: [
        "জানু",
        "ফেব্রু",
        "মার্চ",
        "এপ্রিল",
        "মে",
        "জুন",
        "জুলাই",
        "আগস্ট",
        "সেপ্ট",
        "অক্টো",
        "নভে",
        "ডিসে"
    ],
    abbreviated: [
        "জানু",
        "ফেব্রু",
        "মার্চ",
        "এপ্রিল",
        "মে",
        "জুন",
        "জুলাই",
        "আগস্ট",
        "সেপ্ট",
        "অক্টো",
        "নভে",
        "ডিসে"
    ],
    wide: [
        "জানুয়ারি",
        "ফেব্রুয়ারি",
        "মার্চ",
        "এপ্রিল",
        "মে",
        "জুন",
        "জুলাই",
        "আগস্ট",
        "সেপ্টেম্বর",
        "অক্টোবর",
        "নভেম্বর",
        "ডিসেম্বর"
    ]
};
const dayValues = {
    narrow: [
        "র",
        "সো",
        "ম",
        "বু",
        "বৃ",
        "শু",
        "শ"
    ],
    short: [
        "রবি",
        "সোম",
        "মঙ্গল",
        "বুধ",
        "বৃহ",
        "শুক্র",
        "শনি"
    ],
    abbreviated: [
        "রবি",
        "সোম",
        "মঙ্গল",
        "বুধ",
        "বৃহ",
        "শুক্র",
        "শনি"
    ],
    wide: [
        "রবিবার",
        "সোমবার",
        "মঙ্গলবার",
        "বুধবার",
        "বৃহস্পতিবার ",
        "শুক্রবার",
        "শনিবার"
    ]
};
const dayPeriodValues = {
    narrow: {
        am: "পূ",
        pm: "অপ",
        midnight: "মধ্যরাত",
        noon: "মধ্যাহ্ন",
        morning: "সকাল",
        afternoon: "বিকাল",
        evening: "সন্ধ্যা",
        night: "রাত"
    },
    abbreviated: {
        am: "পূর্বাহ্ন",
        pm: "অপরাহ্ন",
        midnight: "মধ্যরাত",
        noon: "মধ্যাহ্ন",
        morning: "সকাল",
        afternoon: "বিকাল",
        evening: "সন্ধ্যা",
        night: "রাত"
    },
    wide: {
        am: "পূর্বাহ্ন",
        pm: "অপরাহ্ন",
        midnight: "মধ্যরাত",
        noon: "মধ্যাহ্ন",
        morning: "সকাল",
        afternoon: "বিকাল",
        evening: "সন্ধ্যা",
        night: "রাত"
    }
};
const formattingDayPeriodValues = {
    narrow: {
        am: "পূ",
        pm: "অপ",
        midnight: "মধ্যরাত",
        noon: "মধ্যাহ্ন",
        morning: "সকাল",
        afternoon: "বিকাল",
        evening: "সন্ধ্যা",
        night: "রাত"
    },
    abbreviated: {
        am: "পূর্বাহ্ন",
        pm: "অপরাহ্ন",
        midnight: "মধ্যরাত",
        noon: "মধ্যাহ্ন",
        morning: "সকাল",
        afternoon: "বিকাল",
        evening: "সন্ধ্যা",
        night: "রাত"
    },
    wide: {
        am: "পূর্বাহ্ন",
        pm: "অপরাহ্ন",
        midnight: "মধ্যরাত",
        noon: "মধ্যাহ্ন",
        morning: "সকাল",
        afternoon: "বিকাল",
        evening: "সন্ধ্যা",
        night: "রাত"
    }
};
function dateOrdinalNumber(number, localeNumber) {
    if (number > 18 && number <= 31) {
        return localeNumber + "শে";
    } else {
        switch(number){
            case 1:
                return localeNumber + "লা";
            case 2:
            case 3:
                return localeNumber + "রা";
            case 4:
                return localeNumber + "ঠা";
            default:
                return localeNumber + "ই";
        }
    }
}
const ordinalNumber = (dirtyNumber, options)=>{
    const number = Number(dirtyNumber);
    const localeNumber = numberToLocale(number);
    const unit = options?.unit;
    if (unit === "date") {
        return dateOrdinalNumber(number, localeNumber);
    }
    if (number > 10 || number === 0) return localeNumber + "তম";
    const rem10 = number % 10;
    switch(rem10){
        case 2:
        case 3:
            return localeNumber + "য়";
        case 4:
            return localeNumber + "র্থ";
        case 6:
            return localeNumber + "ষ্ঠ";
        default:
            return localeNumber + "ম";
    }
};
function numberToLocale(enNumber) {
    return enNumber.toString().replace(/\d/g, function(match) {
        return numberValues.locale[match];
    });
}
const localize = {
    ordinalNumber,
    era: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: eraValues,
        defaultWidth: "wide"
    }),
    quarter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: quarterValues,
        defaultWidth: "wide",
        argumentCallback: (quarter)=>quarter - 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: monthValues,
        defaultWidth: "wide"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayValues,
        defaultWidth: "wide"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayPeriodValues,
        defaultWidth: "wide",
        formattingValues: formattingDayPeriodValues,
        defaultFormattingWidth: "wide"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn/_lib/match.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "match",
    ()=>match
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchFn.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchPatternFn.js [app-client] (ecmascript)");
;
;
const matchOrdinalNumberPattern = /^(\d+)(ম|য়|র্থ|ষ্ঠ|শে|ই|তম)?/i;
const parseOrdinalNumberPattern = /\d+/i;
const matchEraPatterns = {
    narrow: /^(খ্রিঃপূঃ|খ্রিঃ)/i,
    abbreviated: /^(খ্রিঃপূর্ব|খ্রিঃ)/i,
    wide: /^(খ্রিস্টপূর্ব|খ্রিস্টাব্দ)/i
};
const parseEraPatterns = {
    narrow: [
        /^খ্রিঃপূঃ/i,
        /^খ্রিঃ/i
    ],
    abbreviated: [
        /^খ্রিঃপূর্ব/i,
        /^খ্রিঃ/i
    ],
    wide: [
        /^খ্রিস্টপূর্ব/i,
        /^খ্রিস্টাব্দ/i
    ]
};
const matchQuarterPatterns = {
    narrow: /^[১২৩৪]/i,
    abbreviated: /^[১২৩৪]ত্রৈ/i,
    wide: /^[১২৩৪](ম|য়|র্থ)? ত্রৈমাসিক/i
};
const parseQuarterPatterns = {
    any: [
        /১/i,
        /২/i,
        /৩/i,
        /৪/i
    ]
};
const matchMonthPatterns = {
    narrow: /^(জানু|ফেব্রু|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্ট|অক্টো|নভে|ডিসে)/i,
    abbreviated: /^(জানু|ফেব্রু|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্ট|অক্টো|নভে|ডিসে)/i,
    wide: /^(জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)/i
};
const parseMonthPatterns = {
    any: [
        /^জানু/i,
        /^ফেব্রু/i,
        /^মার্চ/i,
        /^এপ্রিল/i,
        /^মে/i,
        /^জুন/i,
        /^জুলাই/i,
        /^আগস্ট/i,
        /^সেপ্ট/i,
        /^অক্টো/i,
        /^নভে/i,
        /^ডিসে/i
    ]
};
const matchDayPatterns = {
    narrow: /^(র|সো|ম|বু|বৃ|শু|শ)+/i,
    short: /^(রবি|সোম|মঙ্গল|বুধ|বৃহ|শুক্র|শনি)+/i,
    abbreviated: /^(রবি|সোম|মঙ্গল|বুধ|বৃহ|শুক্র|শনি)+/i,
    wide: /^(রবিবার|সোমবার|মঙ্গলবার|বুধবার|বৃহস্পতিবার |শুক্রবার|শনিবার)+/i
};
const parseDayPatterns = {
    narrow: [
        /^র/i,
        /^সো/i,
        /^ম/i,
        /^বু/i,
        /^বৃ/i,
        /^শু/i,
        /^শ/i
    ],
    short: [
        /^রবি/i,
        /^সোম/i,
        /^মঙ্গল/i,
        /^বুধ/i,
        /^বৃহ/i,
        /^শুক্র/i,
        /^শনি/i
    ],
    abbreviated: [
        /^রবি/i,
        /^সোম/i,
        /^মঙ্গল/i,
        /^বুধ/i,
        /^বৃহ/i,
        /^শুক্র/i,
        /^শনি/i
    ],
    wide: [
        /^রবিবার/i,
        /^সোমবার/i,
        /^মঙ্গলবার/i,
        /^বুধবার/i,
        /^বৃহস্পতিবার /i,
        /^শুক্রবার/i,
        /^শনিবার/i
    ]
};
const matchDayPeriodPatterns = {
    narrow: /^(পূ|অপ|মধ্যরাত|মধ্যাহ্ন|সকাল|বিকাল|সন্ধ্যা|রাত)/i,
    abbreviated: /^(পূর্বাহ্ন|অপরাহ্ন|মধ্যরাত|মধ্যাহ্ন|সকাল|বিকাল|সন্ধ্যা|রাত)/i,
    wide: /^(পূর্বাহ্ন|অপরাহ্ন|মধ্যরাত|মধ্যাহ্ন|সকাল|বিকাল|সন্ধ্যা|রাত)/i
};
const parseDayPeriodPatterns = {
    any: {
        am: /^পূ/i,
        pm: /^অপ/i,
        midnight: /^মধ্যরাত/i,
        noon: /^মধ্যাহ্ন/i,
        morning: /সকাল/i,
        afternoon: /বিকাল/i,
        evening: /সন্ধ্যা/i,
        night: /রাত/i
    }
};
const match = {
    ordinalNumber: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildMatchPatternFn"])({
        matchPattern: matchOrdinalNumberPattern,
        parsePattern: parseOrdinalNumberPattern,
        valueCallback: (value)=>parseInt(value, 10)
    }),
    era: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchEraPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseEraPatterns,
        defaultParseWidth: "wide"
    }),
    quarter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchQuarterPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseQuarterPatterns,
        defaultParseWidth: "any",
        valueCallback: (index)=>index + 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchMonthPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseMonthPatterns,
        defaultParseWidth: "any"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchDayPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseDayPatterns,
        defaultParseWidth: "wide"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchDayPeriodPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseDayPeriodPatterns,
        defaultParseWidth: "any"
    })
};
}),
]);

//# sourceMappingURL=0nrf_date-fns_locale_03lpfq5._.js.map