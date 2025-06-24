import deckyPlugin from "@decky/rollup";
import replace from "@rollup/plugin-replace";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const { name, version, author } = require("./package.json");

export default deckyPlugin({
  plugins: [
    replace({
      preventAssignment: true,
      values: {
        "PLUGIN_NAME": name,
        "PLUGIN_VERSION": version,
        "PLUGIN_AUTHOR": typeof author === "object" ? author.name : author,
      },
    }),
  ],
});
