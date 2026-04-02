module.exports = {
  extends: "expo",
  ignorePatterns: ["/dist/", "/.expo/", "/node_modules/"],
  overrides: [
    {
      files: ["scripts/**/*.js"],
      env: { node: true },
    },
  ],
};
