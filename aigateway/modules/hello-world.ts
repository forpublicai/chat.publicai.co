import { ZuploContext, ZuploRequest } from "@zuplo/runtime";

export default async function (request: ZuploRequest, context: ZuploContext) {
  /**
   * Use the log property on context to enjoy
   * logging magic when testing your API.
   */
  context.log.info(`Hi, from inside your zup!`);

  /**
   * If you want to proxy an API, you can simply
   * return the content of a fetch. Try it by
   * uncommenting the line below.
   */
  // return fetch('http://www.example.com/');

  /**
   * In this example, we're just going to return some content.
   */
  return "What zup?";
}
