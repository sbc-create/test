module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "ta",
    ()=>ta
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/formatDistance.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/formatLong.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/formatRelative.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$localize$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/localize.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$match$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/match.js [app-rsc] (ecmascript)");
;
;
;
;
;
const ta = {
    code: "ta",
    formatDistance: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$formatDistance$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatDistance"],
    formatLong: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$formatLong$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatLong"],
    formatRelative: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$formatRelative$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["formatRelative"],
    localize: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$localize$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["localize"],
    match: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$ta$2f$_lib$2f$match$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["match"],
    options: {
        weekStartsOn: 1 /* Monday */ ,
        firstWeekContainsDate: 4
    }
};
const __TURBOPACK__default__export__ = ta;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/formatDistance.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatDistance",
    ()=>formatDistance
]);
function isPluralType(val) {
    return val.one !== undefined;
}
const formatDistanceLocale = {
    lessThanXSeconds: {
        one: {
            default: "ஒரு வினாடிக்கு குறைவாக",
            in: "ஒரு வினாடிக்குள்",
            ago: "ஒரு வினாடிக்கு முன்பு"
        },
        other: {
            default: "{{count}} வினாடிகளுக்கு குறைவாக",
            in: "{{count}} வினாடிகளுக்குள்",
            ago: "{{count}} வினாடிகளுக்கு முன்பு"
        }
    },
    xSeconds: {
        one: {
            default: "1 வினாடி",
            in: "1 வினாடியில்",
            ago: "1 வினாடி முன்பு"
        },
        other: {
            default: "{{count}} விநாடிகள்",
            in: "{{count}} வினாடிகளில்",
            ago: "{{count}} விநாடிகளுக்கு முன்பு"
        }
    },
    halfAMinute: {
        default: "அரை நிமிடம்",
        in: "அரை நிமிடத்தில்",
        ago: "அரை நிமிடம் முன்பு"
    },
    lessThanXMinutes: {
        one: {
            default: "ஒரு நிமிடத்திற்கும் குறைவாக",
            in: "ஒரு நிமிடத்திற்குள்",
            ago: "ஒரு நிமிடத்திற்கு முன்பு"
        },
        other: {
            default: "{{count}} நிமிடங்களுக்கும் குறைவாக",
            in: "{{count}} நிமிடங்களுக்குள்",
            ago: "{{count}} நிமிடங்களுக்கு முன்பு"
        }
    },
    xMinutes: {
        one: {
            default: "1 நிமிடம்",
            in: "1 நிமிடத்தில்",
            ago: "1 நிமிடம் முன்பு"
        },
        other: {
            default: "{{count}} நிமிடங்கள்",
            in: "{{count}} நிமிடங்களில்",
            ago: "{{count}} நிமிடங்களுக்கு முன்பு"
        }
    },
    aboutXHours: {
        one: {
            default: "சுமார் 1 மணி நேரம்",
            in: "சுமார் 1 மணி நேரத்தில்",
            ago: "சுமார் 1 மணி நேரத்திற்கு முன்பு"
        },
        other: {
            default: "சுமார் {{count}} மணி நேரம்",
            in: "சுமார் {{count}} மணி நேரத்திற்கு முன்பு",
            ago: "சுமார் {{count}} மணி நேரத்தில்"
        }
    },
    xHours: {
        one: {
            default: "1 மணி நேரம்",
            in: "1 மணி நேரத்தில்",
            ago: "1 மணி நேரத்திற்கு முன்பு"
        },
        other: {
            default: "{{count}} மணி நேரம்",
            in: "{{count}} மணி நேரத்தில்",
            ago: "{{count}} மணி நேரத்திற்கு முன்பு"
        }
    },
    xDays: {
        one: {
            default: "1 நாள்",
            in: "1 நாளில்",
            ago: "1 நாள் முன்பு"
        },
        other: {
            default: "{{count}} நாட்கள்",
            in: "{{count}} நாட்களில்",
            ago: "{{count}} நாட்களுக்கு முன்பு"
        }
    },
    aboutXWeeks: {
        one: {
            default: "சுமார் 1 வாரம்",
            in: "சுமார் 1 வாரத்தில்",
            ago: "சுமார் 1 வாரம் முன்பு"
        },
        other: {
            default: "சுமார் {{count}} வாரங்கள்",
            in: "சுமார் {{count}} வாரங்களில்",
            ago: "சுமார் {{count}} வாரங்களுக்கு முன்பு"
        }
    },
    xWeeks: {
        one: {
            default: "1 வாரம்",
            in: "1 வாரத்தில்",
            ago: "1 வாரம் முன்பு"
        },
        other: {
            default: "{{count}} வாரங்கள்",
            in: "{{count}} வாரங்களில்",
            ago: "{{count}} வாரங்களுக்கு முன்பு"
        }
    },
    aboutXMonths: {
        one: {
            default: "சுமார் 1 மாதம்",
            in: "சுமார் 1 மாதத்தில்",
            ago: "சுமார் 1 மாதத்திற்கு முன்பு"
        },
        other: {
            default: "சுமார் {{count}} மாதங்கள்",
            in: "சுமார் {{count}} மாதங்களில்",
            ago: "சுமார் {{count}} மாதங்களுக்கு முன்பு"
        }
    },
    xMonths: {
        one: {
            default: "1 மாதம்",
            in: "1 மாதத்தில்",
            ago: "1 மாதம் முன்பு"
        },
        other: {
            default: "{{count}} மாதங்கள்",
            in: "{{count}} மாதங்களில்",
            ago: "{{count}} மாதங்களுக்கு முன்பு"
        }
    },
    aboutXYears: {
        one: {
            default: "சுமார் 1 வருடம்",
            in: "சுமார் 1 ஆண்டில்",
            ago: "சுமார் 1 வருடம் முன்பு"
        },
        other: {
            default: "சுமார் {{count}} ஆண்டுகள்",
            in: "சுமார் {{count}} ஆண்டுகளில்",
            ago: "சுமார் {{count}} ஆண்டுகளுக்கு முன்பு"
        }
    },
    xYears: {
        one: {
            default: "1 வருடம்",
            in: "1 ஆண்டில்",
            ago: "1 வருடம் முன்பு"
        },
        other: {
            default: "{{count}} ஆண்டுகள்",
            in: "{{count}} ஆண்டுகளில்",
            ago: "{{count}} ஆண்டுகளுக்கு முன்பு"
        }
    },
    overXYears: {
        one: {
            default: "1 வருடத்திற்கு மேல்",
            in: "1 வருடத்திற்கும் மேலாக",
            ago: "1 வருடம் முன்பு"
        },
        other: {
            default: "{{count}} ஆண்டுகளுக்கும் மேலாக",
            in: "{{count}} ஆண்டுகளில்",
            ago: "{{count}} ஆண்டுகளுக்கு முன்பு"
        }
    },
    almostXYears: {
        one: {
            default: "கிட்டத்தட்ட 1 வருடம்",
            in: "கிட்டத்தட்ட 1 ஆண்டில்",
            ago: "கிட்டத்தட்ட 1 வருடம் முன்பு"
        },
        other: {
            default: "கிட்டத்தட்ட {{count}} ஆண்டுகள்",
            in: "கிட்டத்தட்ட {{count}} ஆண்டுகளில்",
            ago: "கிட்டத்தட்ட {{count}} ஆண்டுகளுக்கு முன்பு"
        }
    }
};
const formatDistance = (token, count, options)=>{
    const tense = options?.addSuffix ? options.comparison && options.comparison > 0 ? "in" : "ago" : "default";
    const tokenValue = formatDistanceLocale[token];
    if (!isPluralType(tokenValue)) return tokenValue[tense];
    if (count === 1) {
        return tokenValue.one[tense];
    } else {
        return tokenValue.other[tense].replace("{{count}}", String(count));
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/formatLong.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatLong",
    ()=>formatLong
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildFormatLongFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildFormatLongFn.js [app-rsc] (ecmascript)");
;
// Ref: https://www.unicode.org/cldr/charts/32/summary/ta.html
// CLDR #1846 - #1849
const dateFormats = {
    full: "EEEE, d MMMM, y",
    long: "d MMMM, y",
    medium: "d MMM, y",
    short: "d/M/yy"
};
// CLDR #1850 - #1853
const timeFormats = {
    full: "a h:mm:ss zzzz",
    long: "a h:mm:ss z",
    medium: "a h:mm:ss",
    short: "a h:mm"
};
const dateTimeFormats = {
    full: "{{date}} {{time}}",
    long: "{{date}} {{time}}",
    medium: "{{date}}, {{time}}",
    short: "{{date}}, {{time}}"
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
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/formatRelative.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatRelative",
    ()=>formatRelative
]);
const formatRelativeLocale = {
    lastWeek: "'கடந்த' eeee p 'மணிக்கு'",
    yesterday: "'நேற்று ' p 'மணிக்கு'",
    today: "'இன்று ' p 'மணிக்கு'",
    tomorrow: "'நாளை ' p 'மணிக்கு'",
    nextWeek: "eeee p 'மணிக்கு'",
    other: "P"
};
const formatRelative = (token, _date, _baseDate, _options)=>formatRelativeLocale[token];
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/localize.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "localize",
    ()=>localize
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildLocalizeFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildLocalizeFn.js [app-rsc] (ecmascript)");
;
// Ref: https://www.unicode.org/cldr/charts/32/summary/ta.html
const eraValues = {
    narrow: [
        "கி.மு.",
        "கி.பி."
    ],
    abbreviated: [
        "கி.மு.",
        "கி.பி."
    ],
    wide: [
        "கிறிஸ்துவுக்கு முன்",
        "அன்னோ டோமினி"
    ]
};
const quarterValues = {
    // CLDR #1644 - #1647
    narrow: [
        "1",
        "2",
        "3",
        "4"
    ],
    // CLDR #1636 - #1639
    abbreviated: [
        "காலா.1",
        "காலா.2",
        "காலா.3",
        "காலா.4"
    ],
    // CLDR #1628 - #1631
    wide: [
        "ஒன்றாம் காலாண்டு",
        "இரண்டாம் காலாண்டு",
        "மூன்றாம் காலாண்டு",
        "நான்காம் காலாண்டு"
    ]
};
const monthValues = {
    // CLDR #700 - #711
    narrow: [
        "ஜ",
        "பி",
        "மா",
        "ஏ",
        "மே",
        "ஜூ",
        "ஜூ",
        "ஆ",
        "செ",
        "அ",
        "ந",
        "டி"
    ],
    // CLDR #1676 - #1687
    abbreviated: [
        "ஜன.",
        "பிப்.",
        "மார்.",
        "ஏப்.",
        "மே",
        "ஜூன்",
        "ஜூலை",
        "ஆக.",
        "செப்.",
        "அக்.",
        "நவ.",
        "டிச."
    ],
    // CLDR #1652 - #1663
    wide: [
        "ஜனவரி",
        "பிப்ரவரி",
        "மார்ச்",
        "ஏப்ரல்",
        "மே",
        "ஜூன்",
        "ஜூலை",
        "ஆகஸ்ட்",
        "செப்டம்பர்",
        "அக்டோபர்",
        "நவம்பர்",
        "டிசம்பர்"
    ]
};
const dayValues = {
    // CLDR #1766 - #1772
    narrow: [
        "ஞா",
        "தி",
        "செ",
        "பு",
        "வி",
        "வெ",
        "ச"
    ],
    // CLDR #1752 - #1758
    short: [
        "ஞா",
        "தி",
        "செ",
        "பு",
        "வி",
        "வெ",
        "ச"
    ],
    // CLDR #1738 - #1744
    abbreviated: [
        "ஞாயி.",
        "திங்.",
        "செவ்.",
        "புத.",
        "வியா.",
        "வெள்.",
        "சனி"
    ],
    // CLDR #1724 - #1730
    wide: [
        "ஞாயிறு",
        "திங்கள்",
        "செவ்வாய்",
        "புதன்",
        "வியாழன்",
        "வெள்ளி",
        "சனி"
    ]
};
// CLDR #1780 - #1845
const dayPeriodValues = {
    narrow: {
        am: "மு.ப",
        pm: "பி.ப",
        midnight: "நள்.",
        noon: "நண்.",
        morning: "கா.",
        afternoon: "மதி.",
        evening: "மா.",
        night: "இர."
    },
    abbreviated: {
        am: "முற்பகல்",
        pm: "பிற்பகல்",
        midnight: "நள்ளிரவு",
        noon: "நண்பகல்",
        morning: "காலை",
        afternoon: "மதியம்",
        evening: "மாலை",
        night: "இரவு"
    },
    wide: {
        am: "முற்பகல்",
        pm: "பிற்பகல்",
        midnight: "நள்ளிரவு",
        noon: "நண்பகல்",
        morning: "காலை",
        afternoon: "மதியம்",
        evening: "மாலை",
        night: "இரவு"
    }
};
// CLDR #1780 - #1845
const formattingDayPeriodValues = {
    narrow: {
        am: "மு.ப",
        pm: "பி.ப",
        midnight: "நள்.",
        noon: "நண்.",
        morning: "கா.",
        afternoon: "மதி.",
        evening: "மா.",
        night: "இர."
    },
    abbreviated: {
        am: "முற்பகல்",
        pm: "பிற்பகல்",
        midnight: "நள்ளிரவு",
        noon: "நண்பகல்",
        morning: "காலை",
        afternoon: "மதியம்",
        evening: "மாலை",
        night: "இரவு"
    },
    wide: {
        am: "முற்பகல்",
        pm: "பிற்பகல்",
        midnight: "நள்ளிரவு",
        noon: "நண்பகல்",
        morning: "காலை",
        afternoon: "மதியம்",
        evening: "மாலை",
        night: "இரவு"
    }
};
const ordinalNumber = (dirtyNumber, _options)=>{
    return String(dirtyNumber);
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
"[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta/_lib/match.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "match",
    ()=>match
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchFn.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$_lib$2f$buildMatchPatternFn$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/_lib/buildMatchPatternFn.js [app-rsc] (ecmascript)");
;
;
const matchOrdinalNumberPattern = /^(\d+)(வது)?/i;
const parseOrdinalNumberPattern = /\d+/i;
const matchEraPatterns = {
    narrow: /^(கி.மு.|கி.பி.)/i,
    abbreviated: /^(கி\.?\s?மு\.?|கி\.?\s?பி\.?)/,
    wide: /^(கிறிஸ்துவுக்கு\sமுன்|அன்னோ\sடோமினி)/i
};
const parseEraPatterns = {
    any: [
        /கி\.?\s?மு\.?/,
        /கி\.?\s?பி\.?/
    ]
};
const matchQuarterPatterns = {
    narrow: /^[1234]/i,
    abbreviated: /^காலா.[1234]/i,
    wide: /^(ஒன்றாம்|இரண்டாம்|மூன்றாம்|நான்காம்) காலாண்டு/i
};
const parseQuarterPatterns = {
    narrow: [
        /1/i,
        /2/i,
        /3/i,
        /4/i
    ],
    any: [
        /(1|காலா.1|ஒன்றாம்)/i,
        /(2|காலா.2|இரண்டாம்)/i,
        /(3|காலா.3|மூன்றாம்)/i,
        /(4|காலா.4|நான்காம்)/i
    ]
};
const matchMonthPatterns = {
    narrow: /^(ஜ|பி|மா|ஏ|மே|ஜூ|ஆ|செ|அ|ந|டி)$/i,
    abbreviated: /^(ஜன.|பிப்.|மார்.|ஏப்.|மே|ஜூன்|ஜூலை|ஆக.|செப்.|அக்.|நவ.|டிச.)/i,
    wide: /^(ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|மே|ஜூன்|ஜூலை|ஆகஸ்ட்|செப்டம்பர்|அக்டோபர்|நவம்பர்|டிசம்பர்)/i
};
const parseMonthPatterns = {
    narrow: [
        /^ஜ$/i,
        /^பி/i,
        /^மா/i,
        /^ஏ/i,
        /^மே/i,
        /^ஜூ/i,
        /^ஜூ/i,
        /^ஆ/i,
        /^செ/i,
        /^அ/i,
        /^ந/i,
        /^டி/i
    ],
    any: [
        /^ஜன/i,
        /^பி/i,
        /^மா/i,
        /^ஏ/i,
        /^மே/i,
        /^ஜூன்/i,
        /^ஜூலை/i,
        /^ஆ/i,
        /^செ/i,
        /^அ/i,
        /^ந/i,
        /^டி/i
    ]
};
const matchDayPatterns = {
    narrow: /^(ஞா|தி|செ|பு|வி|வெ|ச)/i,
    short: /^(ஞா|தி|செ|பு|வி|வெ|ச)/i,
    abbreviated: /^(ஞாயி.|திங்.|செவ்.|புத.|வியா.|வெள்.|சனி)/i,
    wide: /^(ஞாயிறு|திங்கள்|செவ்வாய்|புதன்|வியாழன்|வெள்ளி|சனி)/i
};
const parseDayPatterns = {
    narrow: [
        /^ஞா/i,
        /^தி/i,
        /^செ/i,
        /^பு/i,
        /^வி/i,
        /^வெ/i,
        /^ச/i
    ],
    any: [
        /^ஞா/i,
        /^தி/i,
        /^செ/i,
        /^பு/i,
        /^வி/i,
        /^வெ/i,
        /^ச/i
    ]
};
const matchDayPeriodPatterns = {
    narrow: /^(மு.ப|பி.ப|நள்|நண்|காலை|மதியம்|மாலை|இரவு)/i,
    any: /^(மு.ப|பி.ப|முற்பகல்|பிற்பகல்|நள்ளிரவு|நண்பகல்|காலை|மதியம்|மாலை|இரவு)/i
};
const parseDayPeriodPatterns = {
    any: {
        am: /^மு/i,
        pm: /^பி/i,
        midnight: /^நள்/i,
        noon: /^நண்/i,
        morning: /காலை/i,
        afternoon: /மதியம்/i,
        evening: /மாலை/i,
        night: /இரவு/i
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

//# sourceMappingURL=0nrf_date-fns_locale_1n-33gy._.js.map