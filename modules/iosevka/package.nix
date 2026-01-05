{
  inputs,
  lib,

  # Deps
  buildNpmPackage,
  importNpmLock,
  remarshal,
  ttfautohint-nox,
  nerd-font-patcher,

  # Options
  variant ? null,
  features ? "ttf", # "full", "ttf" or "ttf-unhinted"
  nerdfont ? false,
  privateBuildPlan ? null,
  extraParameters ? null,

  ...
}:

let
  inherit (lib.strings) concatStringsSep match optionalString;

  # Derived package attributes.
  pname = "Iosevka${variant}";
  src = inputs.iosevka-upstream;
  version = concatStringsSep "-" (match "(.{4})(.{2})(.{2}).*" src.lastModifiedDate);

  targets =
    if (features == "full") then
      "contents::${pname}"
    else if (features == "ttf") then
      "ttf::${pname}"
    else if (features == "ttf-unhinted") then
      "ttf-unhinted::${pname}"
    else
      throw "Unsupported features: ${toString features}";
in

assert (builtins.isAttrs privateBuildPlan) -> builtins.hasAttr "family" privateBuildPlan;
assert (privateBuildPlan != null) -> variant != null;
assert (extraParameters != null) -> variant != null;

buildNpmPackage {
  inherit pname version;
  inherit src;

  npmDeps = importNpmLock {
    npmRoot = src.outPath;
  };

  npmConfigHook = importNpmLock.npmConfigHook;

  nativeBuildInputs = [
    remarshal
    ttfautohint-nox
    nerd-font-patcher
  ];

  buildPlan =
    if builtins.isAttrs privateBuildPlan then
      builtins.toJSON { buildPlans.${pname} = privateBuildPlan; }
    else
      privateBuildPlan;

  inherit extraParameters;
  passAsFile = [
    "extraParameters"
  ]
  ++ lib.optionals (
    !(builtins.isString privateBuildPlan && lib.hasPrefix builtins.storeDir privateBuildPlan)
  ) [ "buildPlan" ];

  configurePhase = ''
    runHook preConfigure
    ${lib.optionalString (builtins.isAttrs privateBuildPlan) ''
      remarshal -i "$buildPlanPath" -o private-build-plans.toml -if json -of toml
    ''}
    ${lib.optionalString
      (builtins.isString privateBuildPlan && (!lib.hasPrefix builtins.storeDir privateBuildPlan))
      ''
        cp "$buildPlanPath" private-build-plans.toml
      ''
    }
    ${lib.optionalString
      (builtins.isString privateBuildPlan && (lib.hasPrefix builtins.storeDir privateBuildPlan))
      ''
        cp "$buildPlan" private-build-plans.toml
      ''
    }
    runHook postConfigure
  '';

  enableParallelBuilding = true;
  buildPhase = ''
    export HOME=$TMPDIR
    runHook preBuild

    # Build everything: TTF + webfont, hinted + unhinted
    npm run build --no-update-notifier --targets ${targets} \
      -- --jCmd=$NIX_BUILD_CORES

    runHook postBuild
  '';

  postBuild = optionalString nerdfont ''
    fontdir="${placeholder "out"}/share/fonts/truetype/NerdFonts"
    mkdir -p "$fontdir"
    for ttf_file in dist/${pname}/TTF/*.ttf; do
        ${lib.getExe nerd-font-patcher} "$ttf_file" --complete --no-progressbars \
              --outputdir "$fontdir"/${pname}
    done
  '';

  installPhase = ''
    runHook preInstall

    fontdir="${placeholder "out"}/share/fonts/truetype"
    mkdir -p "$fontdir"
    install -Dm644 "dist/$pname/TTF"/* "$fontdir"

    ${lib.optionalString (features == "full") ''
      fontdir="${placeholder "out"}/share/fonts/woff2"
      mkdir -p "$fontdir"
      install -Dm644 "dist/$pname/WOFF2"/* "$fontdir"
    ''}

    runHook postInstall
  '';

  meta = {
    homepage = "https://typeof.net/Iosevka/";
    description = "Versatile typeface for code, from code";
    license = lib.licenses.ofl;
    platforms = lib.platforms.all;
    maintainers = with lib.maintainers; [ lemueldls ];
  };
}
