{
  inputs,
  lib,
  pkgs,

  stdenv,
}:

let
  rubify = inputs.rubify.packages.${stdenv.hostPlatform.system}.default;
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
in

pkgs.sarasa-gothic.overrideAttrs (finalAttrs: {
  installPhase = ''
    runHook preInstall

    ${lib.getExe rubify} *.ttc --font ${iosevka.slim}/share/fonts/truetype/IosevkaSlim-Regular.ttf --subset -o dist
    install -Dm644 -t $out/share/fonts/truetype dist/*.ttc

    runHook postInstall
  '';
})
