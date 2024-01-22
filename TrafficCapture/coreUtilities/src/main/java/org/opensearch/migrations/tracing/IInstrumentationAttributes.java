package org.opensearch.migrations.tracing;

import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.metrics.DoubleHistogram;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.LongHistogram;
import io.opentelemetry.api.metrics.LongUpDownCounter;
import io.opentelemetry.api.trace.Span;
import lombok.NonNull;

import java.time.Duration;
import java.util.ArrayList;

public interface IInstrumentationAttributes {
    AttributeKey<Boolean> HAD_EXCEPTION_KEY = AttributeKey.booleanKey("hadException");

    IInstrumentationAttributes getEnclosingScope();

    default Span getCurrentSpan() { return null; }

    default AttributesBuilder fillAttributes(AttributesBuilder builder) {
        return builder;
    }

    Throwable getObservedExceptionToIncludeInMetrics();

    default @NonNull Attributes getPopulatedMetricAttributes(AttributesBuilder attributesBuilder) {
        final var e = getObservedExceptionToIncludeInMetrics();
        return e == null ? attributesBuilder.build() : attributesBuilder.put(HAD_EXCEPTION_KEY, true).build();
    }

    default Attributes getPopulatedSpanAttributes() {
        return getPopulatedSpanAttributes(Attributes.builder());
    }

    default Attributes getPopulatedSpanAttributes(AttributesBuilder builder) {
        return getPopulatedSpanAttributesBuilder(builder).build();
    }

    default AttributesBuilder getPopulatedSpanAttributesBuilder(AttributesBuilder builder) {
        var currentObj = this;
        var stack = new ArrayList<IInstrumentationAttributes>();
        while (currentObj != null) {
            stack.add(currentObj);
            currentObj = currentObj.getEnclosingScope();
        }
        // reverse the order so that the lowest attribute scopes will overwrite the upper ones if there were conflicts
        for (int i=stack.size()-1; i>=0; --i) {
            builder = stack.get(i).fillAttributes(builder);
        }
        return builder;
    }

    default void meterIncrementEvent(LongCounter c) {
        meterIncrementEvent(c, 1);
    }

    default void meterIncrementEvent(LongCounter c, long increment) {
        meterIncrementEvent(c, increment, Attributes.builder());
    }

    default void meterIncrementEvent(LongCounter c, long increment, AttributesBuilder attributesBuilder) {
        try (var scope = new NullableExemplarScope(getCurrentSpan())) {
            c.add(increment, getPopulatedMetricAttributes(attributesBuilder));
        }
    }

    default void meterDeltaEvent(LongUpDownCounter c, long delta) {
        meterDeltaEvent(c, delta, Attributes.builder());
    }

    default void meterDeltaEvent(LongUpDownCounter c, long delta, AttributesBuilder attributesBuilder) {
        try (var scope = new NullableExemplarScope(getCurrentSpan())) {
            var attributes = getPopulatedMetricAttributes(attributesBuilder);
            c.add(delta, attributes);
        }
    }

    default void meterHistogramMillis(DoubleHistogram histogram, Duration value) {
        meterHistogram(histogram, value.toNanos()/1_000_000.0);
    }

    default void meterHistogramMillis(DoubleHistogram histogram, Duration value, AttributesBuilder attributesBuilder) {
        meterHistogram(histogram, value.toNanos()/1_000_000.0, attributesBuilder);
    }

    default void meterHistogram(DoubleHistogram histogram, double value) {
        meterHistogram(histogram, value, Attributes.builder());
    }

    default void meterHistogram(DoubleHistogram histogram, double value, AttributesBuilder attributesBuilder) {
        try (var scope = new NullableExemplarScope(getCurrentSpan())) {
            histogram.record(value, getPopulatedMetricAttributes(attributesBuilder));
        }
    }

    default void meterHistogram(LongHistogram histogram, long value) {
        meterHistogram(histogram, value, Attributes.builder());
    }

    default void meterHistogram(LongHistogram histogram, long value, AttributesBuilder attributesBuilder) {
        try (var scope = new NullableExemplarScope(getCurrentSpan())) {
            histogram.record(value, getPopulatedMetricAttributes(attributesBuilder));
        }
    }

}
