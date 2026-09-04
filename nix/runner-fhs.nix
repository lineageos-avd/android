{ pkgs }:
pkgs.buildFHSEnv {
  name = "lineageos-runner-env";
  targetPkgs = p: with p; [
    bash coreutils findutils gnugrep gnused gawk which file git curl cacert
    gnutar gzip unzip zip python3 nix gh procps util-linux
    glibc stdenv.cc.cc.lib zlib openssl icu krb5 lttng-ust libunwind
  ];
  runScript = "bash";
  profile = ''
    export SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt
    export GIT_SSL_CAINFO=/etc/ssl/certs/ca-bundle.crt
    export LANG=C.UTF-8
    export LC_ALL=C.UTF-8
  '';
}
