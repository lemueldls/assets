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
  iosevka = callPackage ./iosevka { inherit inputs; };
in

sarasa-gothic.overrideAttrs (finalAttrs: {
  installPhase = ''
    runHook preInstall

    ${lib.getExe rubify} *.ttc --font ${iosevka.slim}/share/fonts/truetype/IosevkaSlim-Regular.ttf --subset -o dist
    install -Dm644 -t $out/share/fonts/truetype dist/*.ttc

    runHook postInstall
  '';
})
