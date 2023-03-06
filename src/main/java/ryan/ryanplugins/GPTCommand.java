package ryan.ryanplugins;

import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class GPTCommand implements CommandExecutor {

    public static String[] currentCommands = new String[0];


    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        Player player = (Player)sender;

        if(sender instanceof Player) {

            if(args[0].equals("kill")) { currentCommands = new String[0];return false;}

            String response = Arrays.toString(generateCommands(ArrayToString(args)));
            player.sendMessage(ChatColor.translateAlternateColorCodes('&',response));

            return true;
        }


        return false;
    }

    public static String[] generateCommands(String prompt) {
        String totalPrompt = "You are an expert in writing minecraft commands. The user gives you a prompt and you turn it into minecraft commands for minecraft the game. Don't give any details or explanation about the code you've written, only give the commands. Format it in a list. These commands will be chained into commands blocks and be executed every tick. Prompt: "+prompt+". Commands:";
        try {
            String response = generateResponse(totalPrompt);
            String[] commands = splitter(response);


            return commands;
        } catch (Exception e) {
            System.out.println(e);
        }
        return new String[0];
    }

    private static final String API_URL = "https://chatgpt-api.shn.hk/v1/";

    public static String generateResponse(String prompt) throws IOException {
        // Set up the HTTP connection
        URL url = new URL(API_URL);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Content-Type", "application/json");
        //connection.setRequestProperty("Authorization", "Bearer YOUR_API_KEY");

        // Construct the request body
        String requestBody = "{\"model\": \"gpt-3.5-turbo\", \"messages\": [{\"role\": \"user\", \"content\": \""+prompt+"\"}]}";

        //System.out.println(requestBody);

        // Send the request
        connection.setDoOutput(true);
        OutputStream outputStream = connection.getOutputStream();
        outputStream.write(requestBody.getBytes(StandardCharsets.UTF_8));
        outputStream.flush();
        outputStream.close();

        // Get the response and extract the completion ID
        BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
        String inputLine;
        StringBuilder response = new StringBuilder();
        while ((inputLine = bufferedReader.readLine()) != null) {
            response.append(inputLine);
        }
        bufferedReader.close();

        String responseRaw = response.toString();
        int indexStart = responseRaw.indexOf("\"content\":\"") + "\"content\":\"".length();

        if(indexStart == -1) {
            return "Something went wrong getting the GPT response...";
        }

        responseRaw = responseRaw.substring(indexStart);
        int indexEnd = responseRaw.indexOf("\"},");
        responseRaw = responseRaw.substring(0,indexEnd);
        return responseRaw;


        /*
        String completionId = extractCompletionId(response.toString());

        // Make a GET request to get the generated response
        url = new URL(API_URL + "/" + completionId);
        connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        //connection.setRequestProperty("Authorization", "Bearer " + API_KEY);

        // Get the response
        bufferedReader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
        response = new StringBuilder();
        while ((inputLine = bufferedReader.readLine()) != null) {
            response.append(inputLine);
        }
        bufferedReader.close();

        // Extract the generated response from the JSON
        int start = response.indexOf("\"text\": \"") + 9;
        int end = response.indexOf("\"", start);
        String generatedResponse = response.substring(start, end);

        return generatedResponse;
         */
    }

    private static String extractCompletionId(String response) {
        Pattern pattern = Pattern.compile("\"id\": \"(.*?)\"");
        Matcher matcher = pattern.matcher(response);
        if (matcher.find()) {
            return matcher.group(1);
        } else {
            throw new RuntimeException("Unable to extract completion ID from response: " + response);
        }
    }
    public static String ArrayToString(String[] args) {
        String f = "";
        for(String s : args) {
            f = f + s + " ";
        }
        return f;
    }

    public static String[] splitter(String s) {

        System.out.println(Arrays.toString(s.split("\\r?\\n")));

        String[] commandArray = s.split(Pattern.quote("\\n"));
        for (int i = 0; i < commandArray.length; i++) {
            if(commandArray[i].equals(" ")) {
                commandArray[i] = "";
                continue;
            }

            if(commandArray[i].length() >= 3) {
                commandArray[i] = commandArray[i].replaceAll("^[0-9]+\\.\\s*", "");
                commandArray[i] = formatMinecraftCommand(commandArray[i]);
            }
        }

        System.out.println(Arrays.toString(commandArray));

        return commandArray;
    }
    public static String formatMinecraftCommand(String command) {
        command = command.trim();
        if (command.startsWith("/")) {
            command = command.substring(1);
        }
        return command;
    }
}
