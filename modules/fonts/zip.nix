{
  inputs,
  pkgs,
  callPackage,
}:
let
  asterism = callPackage ./asterism { inherit inputs; };

  ruby = pkgs.callPackage ./asterism/ruby.nix { inherit inputs; };

  python = pkgs.python3.withPackages (ps: [
    ps.fonttools
    ps.brotli
  ]);

  cuts = [
    {
      name = "asterism-text";
      pkg = asterism.text;
      glob = "*.ttf";
    }
    {
      name = "asterism-slim";
      pkg = asterism.slim;
      glob = "*.ttf";
    }
    {
      name = "asterism-code";
      pkg = asterism.code;
      glob = "*.ttf";
    }
    {
      name = "asterism-term";
      pkg = asterism.term;
      glob = "*.ttf";
    }
    {
      name = "asterism-ruby-pinyin";
      pkg = ruby;
      glob = "AsterismRubyPinyin-*.ttf";
    }
    {
      name = "asterism-ruby-romaji";
      pkg = ruby;
      glob = "AsterismRubyRomaji-*.ttf";
    }
  ];

  cutsFile = pkgs.writeText "font-cut-list.json" (builtins.toJSON cuts);
in

pkgs.runCommand "font-archives"
  {
    nativeBuildInputs = [ python ];
  }
  ''
    python ${../meta/archives.py} --out $out --ofl ${../OFL.txt} --cuts ${cutsFile}
  ''
