{
  inputs,
  lib,
  stdenv,

  # Deps
  callPackage,
  sarasa-gothic,
}:

let
  rubify = inputs.rubify.packages.${stdenv.hostPlatform.system}.default;
  asterism = callPackage ./default.nix { inherit inputs; };
in

sarasa-gothic.overrideAttrs (finalAttrs: {
  installPhase = ''
    runHook preInstall

    ${lib.getExe rubify} *.ttc -o . --font ${asterism.slim}/share/fonts/truetype/AsterismSlim-Regular.ttf --ruby pinyin --position top
    ${lib.getExe rubify} *.ttc -o . --font ${asterism.slim}/share/fonts/truetype/AsterismSlim-Regular.ttf --ruby romaji --position bottom
    install -Dm644 -t $out/share/fonts/truetype *.ttc

    runHook postInstall
  '';
})
