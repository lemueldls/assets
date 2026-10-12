{
  inputs,
  lib,
  stdenv,

  # Deps
  callPackage,
  sarasa-gothic,
  python3Packages,
}:
let
  rubify = inputs.rubify.packages.${stdenv.hostPlatform.system}.default;

  asterism = callPackage ./default.nix { inherit inputs; };

  python = python3Packages.python.withPackages (ps: [
    ps.fonttools
    ps.brotli
  ]);
in

stdenv.mkDerivation (finalAttrs: {
  pname = "AsterismRuby";
  inherit (sarasa-gothic) version;

  dontUnpack = true;

  nativeBuildInputs = [
    rubify
    python
  ];

  buildPhase = ''
    runHook preBuild

    mkdir -p work

    for ruby in pinyin romaji; do
      for ttc in ${sarasa-gothic}/share/fonts/truetype/Sarasa-*.ttc; do
        rubify "$ttc" -o "work/$ruby" \
          --font ${asterism.slim}/share/fonts/truetype/AsterismSlim-Regular.ttf \
          --ruby "$ruby" \
          --position $([ "$ruby" = pinyin ] && echo top || echo bottom) \
          --split --subset --woff2
      done
    done

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    for ruby in Pinyin Romaji; do
      python ${../../meta/ruby.py} --work "work/$(echo $ruby | tr 'A-Z' 'a-z')" \
        --asterism ${asterism.text}/share/fonts/truetype \
        --out "$out/share/fonts" \
        --family "Asterism Ruby" \
        --patch "$ruby"
    done

    runHook postInstall
  '';

  meta = {
    description = "Asterism annotated with pinyin and romaji ruby";
    license = lib.licenses.ofl;
    platforms = lib.platforms.all;
  };
})
