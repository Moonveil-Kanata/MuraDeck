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
        "__PLUGIN_NAME__": name,
        "__PLUGIN_VERSION__": version,
        "__PLUGIN_AUTHOR__": typeof author === "object" ? author.name : author,
      },
    }),
  ],
});
