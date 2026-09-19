import { renderToStaticMarkup } from "react-dom/server";
import DoorTrace from "./components/DoorTrace";
import payload from "./__payload.json";
const bad = payload.rows.find((r) => r.prediction !== "Normal");
console.log(renderToStaticMarkup(
  <DoorTrace trace={bad.evidence.trace} regions={bad.evidence.regions}
             status={bad.prediction} startClock={bad.evidence.start_clock} />));
