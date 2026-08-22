module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "id",
    ()=>id
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/formatDistance.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/formatLong.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/formatRelative.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$localize$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/localize.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$match$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/match.js [app-ssr] (ecmascript)");
;
;
;
;
;
const id = {
    code: "id",
    formatDistance: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["formatDistance"],
    formatLong: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["formatLong"],
    formatRelative: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["formatRelative"],
    localize: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$localize$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["localize"],
    match: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$id$2f$_lib$2f$match$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["match"],
    options: {
        weekStartsOn: 1 /* Monday */ ,
        firstWeekContainsDate: 1
    }
};
const __TURBOPACK__default__export__ = id;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/formatDistance.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatDistance",
    ()=>formatDistance
]);
const formatDistanceLocale = {
    lessThanXSeconds: {
        one: "kurang dari 1 detik",
        other: "kurang dari {{count}} detik"
    },
    xSeconds: {
        one: "1 detik",
        other: "{{count}} detik"
    },
    halfAMinute: "setengah menit",
    lessThanXMinutes: {
        one: "kurang dari 1 menit",
        other: "kurang dari {{count}} menit"
    },
    xMinutes: {
        one: "1 menit",
        other: "{{count}} menit"
    },
    aboutXHours: {
        one: "sekitar 1 jam",
        other: "sekitar {{count}} jam"
    },
    xHours: {
        one: "1 jam",
        other: "{{count}} jam"
    },
    xDays: {
        one: "1 hari",
        other: "{{count}} hari"
    },
    aboutXWeeks: {
        one: "sekitar 1 minggu",
        other: "sekitar {{count}} minggu"
    },
    xWeeks: {
        one: "1 minggu",
        other: "{{count}} minggu"
    },
    aboutXMonths: {
        one: "sekitar 1 bulan",
        other: "sekitar {{count}} bulan"
    },
    xMonths: {
        one: "1 bulan",
        other: "{{count}} bulan"
    },
    aboutXYears: {
        one: "sekitar 1 tahun",
        other: "sekitar {{count}} tahun"
    },
    xYears: {
        one: "1 tahun",
        other: "{{count}} tahun"
    },
    overXYears: {
        one: "lebih dari 1 tahun",
        other: "lebih dari {{count}} tahun"
    },
    almostXYears: {
        one: "hampir 1 tahun",
        other: "hampir {{count}} tahun"
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
            return "dalam waktu " + result;
        } else {
            return result + " yang lalu";
        }
    }
    return result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/formatLong.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatLong",
    ()=>formatLong
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildFormatLongFn.js [app-ssr] (ecmascript)");
;
const dateFormats = {
    full: "EEEE, d MMMM yyyy",
    long: "d MMMM yyyy",
    medium: "d MMM yyyy",
    short: "d/M/yyyy"
};
const timeFormats = {
    full: "HH.mm.ss",
    long: "HH.mm.ss",
    medium: "HH.mm",
    short: "HH.mm"
};
const dateTimeFormats = {
    full: "{{date}} 'pukul' {{time}}",
    long: "{{date}} 'pukul' {{time}}",
    medium: "{{date}}, {{time}}",
    short: "{{date}}, {{time}}"
};
const formatLong = {
    date: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: dateFormats,
        defaultWidth: "full"
    }),
    time: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: timeFormats,
        defaultWidth: "full"
    }),
    dateTime: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildFormatLongFn"])({
        formats: dateTimeFormats,
        defaultWidth: "full"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/formatRelative.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatRelative",
    ()=>formatRelative
]);
const formatRelativeLocale = {
    lastWeek: "eeee 'lalu pukul' p",
    yesterday: "'Kemarin pukul' p",
    today: "'Hari ini pukul' p",
    tomorrow: "'Besok pukul' p",
    nextWeek: "eeee 'pukul' p",
    other: "P"
};
const formatRelative = (token, _date, _baseDate, _options)=>formatRelativeLocale[token];
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/localize.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "localize",
    ()=>localize
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildLocalizeFn.js [app-ssr] (ecmascript)");
;
// All data for localization are taken from this page
// https://www.unicode.org/cldr/charts/32/summary/id.html
const eraValues = {
    narrow: [
        "SM",
        "M"
    ],
    abbreviated: [
        "SM",
        "M"
    ],
    wide: [
        "Sebelum Masehi",
        "Masehi"
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
        "K1",
        "K2",
        "K3",
        "K4"
    ],
    wide: [
        "Kuartal ke-1",
        "Kuartal ke-2",
        "Kuartal ke-3",
        "Kuartal ke-4"
    ]
};
// Note: in Indonesian, the names of days of the week and months are capitalized.
// If you are making a new locale based on this one, check if the same is true for the language you're working on.
// Generally, formatted dates should look like they are in the middle of a sentence,
// e.g. in Spanish language the weekdays and months should be in the lowercase.
const monthValues = {
    narrow: [
        "J",
        "F",
        "M",
        "A",
        "M",
        "J",
        "J",
        "A",
        "S",
        "O",
        "N",
        "D"
    ],
    abbreviated: [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "Mei",
        "Jun",
        "Jul",
        "Agt",
        "Sep",
        "Okt",
        "Nov",
        "Des"
    ],
    wide: [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember"
    ]
};
const dayValues = {
    narrow: [
        "M",
        "S",
        "S",
        "R",
        "K",
        "J",
        "S"
    ],
    short: [
        "Min",
        "Sen",
        "Sel",
        "Rab",
        "Kam",
        "Jum",
        "Sab"
    ],
    abbreviated: [
        "Min",
        "Sen",
        "Sel",
        "Rab",
        "Kam",
        "Jum",
        "Sab"
    ],
    wide: [
        "Minggu",
        "Senin",
        "Selasa",
        "Rabu",
        "Kamis",
        "Jumat",
        "Sabtu"
    ]
};
const dayPeriodValues = {
    narrow: {
        am: "AM",
        pm: "PM",
        midnight: "tengah malam",
        noon: "tengah hari",
        morning: "pagi",
        afternoon: "siang",
        evening: "sore",
        night: "malam"
    },
    abbreviated: {
        am: "AM",
        pm: "PM",
        midnight: "tengah malam",
        noon: "tengah hari",
        morning: "pagi",
        afternoon: "siang",
        evening: "sore",
        night: "malam"
    },
    wide: {
        am: "AM",
        pm: "PM",
        midnight: "tengah malam",
        noon: "tengah hari",
        morning: "pagi",
        afternoon: "siang",
        evening: "sore",
        night: "malam"
    }
};
const formattingDayPeriodValues = {
    narrow: {
        am: "AM",
        pm: "PM",
        midnight: "tengah malam",
        noon: "tengah hari",
        morning: "pagi",
        afternoon: "siang",
        evening: "sore",
        night: "malam"
    },
    abbreviated: {
        am: "AM",
        pm: "PM",
        midnight: "tengah malam",
        noon: "tengah hari",
        morning: "pagi",
        afternoon: "siang",
        evening: "sore",
        night: "malam"
    },
    wide: {
        am: "AM",
        pm: "PM",
        midnight: "tengah malam",
        noon: "tengah hari",
        morning: "pagi",
        afternoon: "siang",
        evening: "sore",
        night: "malam"
    }
};
const ordinalNumber = (dirtyNumber, _options)=>{
    const number = Number(dirtyNumber);
    // Can't use "pertama", "kedua" because can't be parsed
    return "ke-" + number;
};
const localize = {
    ordinalNumber,
    era: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: eraValues,
        defaultWidth: "wide"
    }),
    quarter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: quarterValues,
        defaultWidth: "wide",
        argumentCallback: (quarter)=>quarter - 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: monthValues,
        defaultWidth: "wide"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayValues,
        defaultWidth: "wide"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildLocalizeFn"])({
        values: dayPeriodValues,
        defaultWidth: "wide",
        formattingValues: formattingDayPeriodValues,
        defaultFormattingWidth: "wide"
    })
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id/_lib/match.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "match",
    ()=>match
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchFn.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchPatternFn.js [app-ssr] (ecmascript)");
;
;
const matchOrdinalNumberPattern = /^ke-(\d+)?/i;
const parseOrdinalNumberPattern = /\d+/i;
const matchEraPatterns = {
    narrow: /^(sm|m)/i,
    abbreviated: /^(s\.?\s?m\.?|s\.?\s?e\.?\s?u\.?|m\.?|e\.?\s?u\.?)/i,
    wide: /^(sebelum masehi|sebelum era umum|masehi|era umum)/i
};
const parseEraPatterns = {
    any: [
        /^s/i,
        /^(m|e)/i
    ]
};
const matchQuarterPatterns = {
    narrow: /^[1234]/i,
    abbreviated: /^K-?\s[1234]/i,
    wide: /^Kuartal ke-?\s?[1234]/i
};
const parseQuarterPatterns = {
    any: [
        /1/i,
        /2/i,
        /3/i,
        /4/i
    ]
};
const matchMonthPatterns = {
    narrow: /^[jfmasond]/i,
    abbreviated: /^(jan|feb|mar|apr|mei|jun|jul|agt|sep|okt|nov|des)/i,
    wide: /^(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)/i
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
        /^a/i,
        /^s/i,
        /^o/i,
        /^n/i,
        /^d/i
    ],
    any: [
        /^ja/i,
        /^f/i,
        /^ma/i,
        /^ap/i,
        /^me/i,
        /^jun/i,
        /^jul/i,
        /^ag/i,
        /^s/i,
        /^o/i,
        /^n/i,
        /^d/i
    ]
};
const matchDayPatterns = {
    narrow: /^[srkjm]/i,
    short: /^(min|sen|sel|rab|kam|jum|sab)/i,
    abbreviated: /^(min|sen|sel|rab|kam|jum|sab)/i,
    wide: /^(minggu|senin|selasa|rabu|kamis|jumat|sabtu)/i
};
const parseDayPatterns = {
    narrow: [
        /^m/i,
        /^s/i,
        /^s/i,
        /^r/i,
        /^k/i,
        /^j/i,
        /^s/i
    ],
    any: [
        /^m/i,
        /^sen/i,
        /^sel/i,
        /^r/i,
        /^k/i,
        /^j/i,
        /^sa/i
    ]
};
const matchDayPeriodPatterns = {
    narrow: /^(a|p|tengah m|tengah h|(di(\swaktu)?) (pagi|siang|sore|malam))/i,
    any: /^([ap]\.?\s?m\.?|tengah malam|tengah hari|(di(\swaktu)?) (pagi|siang|sore|malam))/i
};
const parseDayPeriodPatterns = {
    any: {
        am: /^a/i,
        pm: /^pm/i,
        midnight: /^tengah m/i,
        noon: /^tengah h/i,
        morning: /pagi/i,
        afternoon: /siang/i,
        evening: /sore/i,
        night: /malam/i
    }
};
const match = {
    ordinalNumber: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildMatchPatternFn"])({
        matchPattern: matchOrdinalNumberPattern,
        parsePattern: parseOrdinalNumberPattern,
        valueCallback: (value)=>parseInt(value, 10)
    }),
    era: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchEraPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseEraPatterns,
        defaultParseWidth: "any"
    }),
    quarter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchQuarterPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseQuarterPatterns,
        defaultParseWidth: "any",
        valueCallback: (index)=>index + 1
    }),
    month: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchMonthPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseMonthPatterns,
        defaultParseWidth: "any"
    }),
    day: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchDayPatterns,
        defaultMatchWidth: "wide",
        parsePatterns: parseDayPatterns,
        defaultParseWidth: "any"
    }),
    dayPeriod: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["buildMatchFn"])({
        matchPatterns: matchDayPeriodPatterns,
        defaultMatchWidth: "any",
        parsePatterns: parseDayPeriodPatterns,
        defaultParseWidth: "any"
    })
};
}),
];

//# sourceMappingURL=0nrf_date-fns_locale_0i7foyl._.js.map