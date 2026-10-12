{
  inputs,
  pkgs,
  callPackage,
}:
let
  asterism = callPackage ./asterism { inherit inputs; };

  ruby = pkgs.callPackage ./asterism/ruby.nix { inherit inputs; };

  archives = [
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
in

pkgs.runCommand "font-archives"
  {
    nativeBuildInputs = [ pkgs.zip ];
  }
  ''
    mkdir -p $out work

    ${pkgs.lib.concatStringsSep "\n" (
      map (
        {
          name,
          pkg,
          glob,
        }:
        ''
            mkdir -p work/${name}
            cp ${pkg}/share/fonts/truetype/${glob} work/${name}/
            cp ${./OFL.txt} work/${name}/OFL.txt
            chmod -R u+w work/${name}
          (cd work/${name} && zip -0 -q -r $out/${name}.zip .)
        ''
      ) archives
    )}
  ''
