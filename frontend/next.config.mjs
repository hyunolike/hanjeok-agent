/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,

  /**
   * 모든 화면이 `/{lang}/...` 아래로 옮겨 갔다. 언어 없는 예전 주소는 기본 언어로 보낸다.
   *
   * `/evidence` 는 README 가 **이미 공개한 링크**라(`agent.hanjeok.com/evidence`) 404 가
   * 되면 밖에 나가 있는 링크가 끊긴다. 307 인 이유는 기본 언어가 바뀔 수 있어서다 —
   * 308 은 브라우저가 영구히 캐시하므로 나중에 되돌릴 수 없다.
   */
  redirects() {
    return [
      { source: '/', destination: '/ko', permanent: false },
      { source: '/evidence', destination: '/ko/evidence', permanent: false },
      { source: '/course/:uuid', destination: '/ko/course/:uuid', permanent: false },
    ]
  },
}
