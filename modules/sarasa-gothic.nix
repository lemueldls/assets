{
  inputs,
  lib,
  stdenv,
  fetchurl,

  # Deps
  callPackage,
  sarasa-gothic,
}:

let
  rubify = inputs.rubify.packages.${stdenv.hostPlatform.system}.default;
  iosevka = callPackage ./iosevka { inherit inputs; };
in

sarasa-gothic.overrideAttrs (finalAttrs: {
  installPhase = ''
    runHook preInstall

    ${lib.getExe rubify} *.ttc -o phase1 --ruby pinyin --position top --font ${iosevka.slim}/share/fonts/truetype/IosevkaSlim-Regular.ttf
    ${lib.getExe rubify} phase1/*.ttc -o phase2 --ruby romaji --position bottom --font ${iosevka.slim}/share/fonts/truetype/IosevkaSlim-Regular.ttf
    install -Dm644 -t $out/share/fonts/truetype phase2/*.ttc

    runHook postInstall
  '';
})
