import { Range } from "react-range";

type Props = {
  min: number;
  max: number;
  step?: number;
  values: [number, number];
  onChange: (values: [number, number]) => void;
};

const sliderTrack = "h-1 bg-border rounded";
const sliderThumb = "w-4 h-4 bg-primary rounded-full focus:outline-none";

export default function YearRangeSlider({
  min,
  max,
  step = 1,
  values,
  onChange,
}: Props) {
  return (
    <div className="w-full ">
      <label className="text-sm font-medium text-foreground ">
        Release Year
      </label>
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1 ">
        <span>{values[0]}</span>
        <span>{values[1]}</span>
      </div>
      <div className="pl-2 pr-2 pt-1">
        <Range
          values={values}
          step={step}
          min={min}
          max={max}
          onChange={(vals) => onChange([vals[0], vals[1]])}
          renderTrack={({ props, children }) => {
            const [minVal, maxVal] = values;
            const percentLeft = ((minVal - min) / (max - min)) * 100;
            const percentRight = ((maxVal - min) / (max - min)) * 100;

            return (
              <div
                {...props}
                className={`w-full ${sliderTrack}`}
                style={{
                  ...props.style,
                  background: `linear-gradient(
          to right,
          #e2e8f0 0%,
          #e2e8f0 ${percentLeft}%,
          #1e293b ${percentLeft}%,
          #1e293b ${percentRight}%,
          #e2e8f0 ${percentRight}%,
          #e2e8f0 100%
        )`,
                }}
              >
                {children}
              </div>
            );
          }}
          renderThumb={({ index, props }) => (
            <div
              key={index}
              {...Object.fromEntries(
                Object.entries(props).filter(([k]) => k !== "key")
              )}
              className={sliderThumb}
            />
          )}
        />
      </div>
    </div>
  );
}
