// F:\Python\PyLab\js\day_separator.js
window.DaySeparator = (function() {
    var SECONDS_PER_DAY = 86400;
    var WEEKEND_GAP_SECONDS = 43200;
    var MIN_SEPARATOR_SPACING_SECONDS = 21600;

    var container = null;
    var times = [];
    var lines = [];

    function clear() {
        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
        }
        container = null;
        times = [];
        lines = [];
    }

    function computeTimes(candleTimes) {
        var result = [];
        if (!candleTimes || candleTimes.length === 0) return result;
        var lastLineTime = 0;

        for (var i = 1; i < candleTimes.length; i++) {
            var prevSec = candleTimes[i - 1];
            var currSec = candleTimes[i];

            var prevUtcDay = Math.floor(prevSec / SECONDS_PER_DAY);
            var currUtcDay = Math.floor(currSec / SECONDS_PER_DAY);

            var isUtcDayChange = (currUtcDay !== prevUtcDay);
            var isWeekendGap = (currSec - prevSec > WEEKEND_GAP_SECONDS);
            var isTooClose = (lastLineTime > 0 && (currSec - lastLineTime) < MIN_SEPARATOR_SPACING_SECONDS);

            if ((isUtcDayChange || isWeekendGap) && !isTooClose) {
                lastLineTime = currSec;
                result.push(currSec);
            }
        }
        return result;
    }

    function init(chartObj, hostEl, candleTimes) {
        if (!chartObj || !hostEl) return;
        clear();

        times = computeTimes(candleTimes);

        container = document.createElement('div');
        container.style.position = 'absolute';
        container.style.top = '0';
        container.style.left = '0';
        container.style.width = '100%';
        container.style.height = '100%';
        container.style.pointerEvents = 'none';
        container.style.zIndex = '5';
        hostEl.style.position = 'relative';
        hostEl.appendChild(container);

        for (var j = 0; j < times.length; j++) {
            var div = document.createElement('div');
            div.style.position = 'absolute';
            div.style.top = '0';
            div.style.bottom = '26px'; // Über der Zeitleiste stoppen
            div.style.width = '0';
            div.style.borderLeft = '1px dashed rgba(33, 150, 243, 0.45)';
            div.style.pointerEvents = 'none';
            container.appendChild(div);
            lines.push(div);
        }

        function update() {
            if (!chartObj || !chartObj.timeScale) return;
            for (var i = 0; i < times.length && i < lines.length; i++) {
                var x = chartObj.timeScale().timeToCoordinate(times[i]);
                if (x === null || x === undefined || isNaN(x)) {
                    lines[i].style.display = 'none';
                } else {
                    lines[i].style.display = 'block';
                    lines[i].style.left = Math.round(x) + 'px';
                }
            }
        }

        chartObj.timeScale().subscribeVisibleLogicalRangeChange(update);
        chartObj.timeScale().subscribeSizeChange(update);

        setTimeout(update, 50);
        setTimeout(update, 200);
    }

    return { init: init, clear: clear };
})();